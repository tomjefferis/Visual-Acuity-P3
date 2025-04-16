"""
PsychoPy script for an RSVP (Rapid Serial Visual Presentation) experiment with adaptive staircase.
Presents streams of letters (target) and numbers (distractors).
First adjusts the size until threshold, then adjusts contrast.
Size decreases after correct responses, stays the same after one error, and increases after two consecutive errors.
Contrast follows the same staircase procedure after size threshold is determined.
Runs separate blocks for left and right eyes.
"""

from psychopy import core, visual, gui, data, event, logging, monitors
import random
import os
import csv
import numpy as np
from datetime import datetime
import serial

try:
    from psychopy import parallel
    PARALLEL_PORT_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    PARALLEL_PORT_AVAILABLE = False
    print("WARNING: Parallel port module not available. EEG triggers will be simulated.")

# --- Constants ---
TARGET_LETTERS = ['C', 'D', 'H', 'K', 'N', 'F', 'R', 'S', 'V', 'Z']
DISTRACTORS = [str(i) for i in range(1, 10)]
N_STREAM_ITEMS = 16
TARGET_POS_MIN = 3 
TARGET_POS_MAX = 8 
FIXATION_PRE_STREAM_DUR = 0.700 
FIXATION_POST_STREAM_RESPONSE_DUR = 0.5 
FIXATION_POST_STREAM_NO_RESPONSE_DUR = 1.000 

# --- Trigger Values ---
# New trigger codes to avoid conflicts with stimulus-specific triggers
TRIGGER_STREAM_START = 100    # First item onset
TRIGGER_TARGET_ONSET = 200    # Target presentation 
TRIGGER_STREAM_END = 300      # End of stream (post-stream fixation onset)

# Dictionary mapping stimuli to trigger values
TRIGGER_MAP = {
    # Number stimuli (distractors)
    '1': 1,
    '2': 2,
    '3': 3,
    '4': 4,
    '5': 5,
    '6': 6,
    '7': 7,
    '8': 8,
    '9': 9,
    # Letter stimuli (targets)
    'C': 10,
    'D': 11,
    'H': 12,
    'K': 13,
    'N': 14,
    'F': 15,
    'R': 16,
    'S': 17,
    'V': 18,
    'Z': 19
}

TRIGGER_DURATION_MS = 10    # Duration to keep trigger on (in ms)

# Serial port configuration for trigger device
SERIAL_PORT_AVAILABLE = True
SERIAL_PORT_NAME = 'COM3'  # Default port name, may need adjustment for the system
SERIAL_BAUD_RATE = 115200  # Default baud rate, adjust based on the device

# --- Item Duration ---
# Will determine item duration in frames based on measured refresh rate
ITEM_DURATION_MS = 100  # Target duration in milliseconds
PRACTICE_SPEED_FACTOR = 1  # Practice speed

# --- Staircase Parameters ---
N_PRACTICE_TRIALS = 2
N_REVERSALS_SIZE = 2        # Number of reversals to complete size staircase
N_REVERSALS_CONTRAST = 2    # Number of reversals to complete contrast staircase
MAX_CONSECUTIVE_ERRORS = 2  # Two consecutive errors cause size/contrast increase
MIN_TRIALS_PER_STAIRCASE = 10  # Minimum trials before staircase can terminate
SIZE_LOGMAR_START = 1.0     # Starting LogMAR value (relatively large letter)
CONTRAST_START_PCT = 100    # Starting contrast percentage (maximum contrast)

# Paths
DATA_FOLDER = 'data'        # Folder to save data files

# --- Initialize serial port ---
def initialize_serial_port():
    """Initialize the serial port for sending triggers to BioSemi/LabJack."""
    if SERIAL_PORT_AVAILABLE:
        try:
            ser = serial.Serial(
                port=SERIAL_PORT_NAME,
                baudrate=SERIAL_BAUD_RATE
            )
            # Reset to zero
            ser.write(bytes([0]))
            print(f"Serial port initialized at {SERIAL_PORT_NAME}, baudrate {SERIAL_BAUD_RATE}")
            return ser
        except Exception as e:
            print(f"WARNING: Failed to initialize serial port: {e}")
            print("EEG triggers will be simulated.")
            return None
    return None

# --- Send trigger function ---
def send_trigger(port, trigger_value):
    """Send a trigger value to the serial port."""
    if port is not None and SERIAL_PORT_AVAILABLE:
        port.write(bytes([trigger_value]))
        logging.exp(f"TRIGGER: Sent value {trigger_value} to serial port")
        # No delay needed - just reset immediately
        port.write(bytes([0]))  # Reset trigger
    else:
        logging.exp(f"TRIGGER: Simulated sending value {trigger_value} to serial port")

# --- LogMAR Conversion ---
def logmar_to_degrees(logmar_value):
    """
    Convert LogMAR value to degrees of visual angle.
    
    LogMAR = log10(MAR), where MAR = size in arcmin / 5
    So, size in arcmin = 5 * 10^LogMAR
    Then convert arcmin to degrees (1 degree = 60 arcmin)
    
    Args:
        logmar_value (float): The LogMAR value to convert
        
    Returns:
        float: Size in degrees of visual angle
    """
    size_arcmin = 5 * (10 ** logmar_value)
    size_degrees = size_arcmin / 60.0
    
    return size_degrees

# --- Michelson Contrast Conversion ---
def contrast_pct_to_color_value(contrast_pct, background_color=0):
    """
    Convert contrast percentage to PsychoPy color value.
    
    Args:
        contrast_pct (float): Contrast percentage (0-100)
        background_color (float): Background color value (-1 to 1 in PsychoPy)
        
    Returns:
        float: Color value for stimulus (-1 to 1 in PsychoPy)
    """
    # Convert percentage to proportion (0-1)
    contrast = contrast_pct / 100.0
    
    # In PsychoPy's -1 to 1 scale, where 0 is mid-gray
    bg = background_color
    
    # For dark stimuli on light background
    stim_color = bg - contrast * (1 - bg)
    
    return stim_color

# --- Staircase Size Class ---
class SizeStaircase:
    """Class to manage size staircase procedure"""
    def __init__(self, logmar_values, starting_logmar=SIZE_LOGMAR_START):
        self.logmar_values = sorted(logmar_values, reverse=True)  # Sort from largest to smallest
        self.current_index = None
        
        # Find starting index based on starting LogMAR
        for i, logmar in enumerate(self.logmar_values):
            if float(logmar) <= starting_logmar:
                self.current_index = i
                break
        
        if self.current_index is None:
            self.current_index = 0  # Default to largest size if starting value not found
            
        self.last_response_correct = None
        self.consecutive_errors = 0
        self.reversal_count = 0
        self.reversal_points = []
        self.direction = None  # None = not set, 1 = increasing, -1 = decreasing
        self.trials = 0
        self.responses = []  # track all responses for analysis
    
    def get_current_logmar(self):
        """Get current LogMAR value"""
        return float(self.logmar_values[self.current_index])
    
    def get_current_size_deg(self):
        """Get current size in degrees"""
        return logmar_to_degrees(self.get_current_logmar())
    
    def record_response(self, correct):
        """
        Record response and adjust staircase
        
        Args:
            correct (bool): Whether response was correct
            
        Returns:
            dict: Information about the update
        """
        self.trials += 1
        self.responses.append(correct)
        
        old_index = self.current_index
        old_direction = self.direction
        
        # Calculate new index
        if correct:
            # Reset consecutive errors
            self.consecutive_errors = 0
            
            # Move to smaller size (if not already at smallest)
            if self.current_index < len(self.logmar_values) - 1:
                if self.direction == 1:  # Was increasing, now decreasing = reversal
                    self.reversal_count += 1
                    self.reversal_points.append((self.trials, self.get_current_logmar()))
                self.direction = -1  # Decreasing
                self.current_index += 1
        else:
            # Increment error counter
            self.consecutive_errors += 1
            
            # If two consecutive errors, increase size
            if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                if self.current_index > 0:  # Not already at largest
                    if self.direction == -1:  # Was decreasing, now increasing = reversal
                        self.reversal_count += 1
                        self.reversal_points.append((self.trials, self.get_current_logmar()))
                    self.direction = 1  # Increasing
                    self.current_index -= 1
                self.consecutive_errors = 0  # Reset after adjustment
        
        self.last_response_correct = correct
        
        return {
            "old_index": old_index,
            "new_index": self.current_index,
            "old_direction": old_direction,
            "new_direction": self.direction,
            "reversal": old_direction is not None and old_direction != self.direction,
            "reversal_count": self.reversal_count
        }
    
    def is_complete(self):
        """Check if staircase is complete (reached reversal threshold)"""
        return (self.reversal_count >= N_REVERSALS_SIZE and 
                self.trials >= MIN_TRIALS_PER_STAIRCASE)
    
    def get_threshold(self):
        """Calculate threshold as mean of last N reversal points"""
        if len(self.reversal_points) >= N_REVERSALS_SIZE:
            # Get LogMAR values from the last N_REVERSALS_SIZE reversal points
            last_reversals = [point[1] for point in self.reversal_points[-N_REVERSALS_SIZE:]]
            return np.mean(last_reversals)
        else:
            # Not enough reversal points, return current value
            return self.get_current_logmar()

# --- Staircase Contrast Class ---
class ContrastStaircase:
    """Class to manage contrast staircase procedure"""
    def __init__(self, contrast_values, starting_contrast=CONTRAST_START_PCT):
        self.contrast_values = sorted(contrast_values, reverse=True)  # Sort from highest to lowest
        self.current_index = None
        
        # Find starting index based on starting contrast
        for i, contrast in enumerate(self.contrast_values):
            if float(contrast) <= starting_contrast:
                self.current_index = i
                break
        
        if self.current_index is None:
            self.current_index = 0  # Default to highest contrast if starting value not found
            
        self.last_response_correct = None
        self.consecutive_errors = 0
        self.reversal_count = 0
        self.reversal_points = []
        self.direction = None  # None = not set, 1 = increasing, -1 = decreasing
        self.trials = 0
        self.responses = []  # track all responses for analysis
    
    def get_current_contrast(self):
        """Get current contrast percentage"""
        return float(self.contrast_values[self.current_index])
    
    def get_current_color_value(self, background_color=0):
        """Get current PsychoPy color value"""
        return contrast_pct_to_color_value(self.get_current_contrast(), background_color)
    
    def record_response(self, correct):
        """
        Record response and adjust staircase
        
        Args:
            correct (bool): Whether response was correct
            
        Returns:
            dict: Information about the update
        """
        self.trials += 1
        self.responses.append(correct)
        
        old_index = self.current_index
        old_direction = self.direction
        
        # Calculate new index
        if correct:
            # Reset consecutive errors
            self.consecutive_errors = 0
            
            # Move to lower contrast (if not already at lowest)
            if self.current_index < len(self.contrast_values) - 1:
                if self.direction == 1:  # Was increasing, now decreasing = reversal
                    self.reversal_count += 1
                    self.reversal_points.append((self.trials, self.get_current_contrast()))
                self.direction = -1  # Decreasing
                self.current_index += 1
        else:
            # Increment error counter
            self.consecutive_errors += 1
            
            # If two consecutive errors, increase contrast
            if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                if self.current_index > 0:  # Not already at highest
                    if self.direction == -1:  # Was decreasing, now increasing = reversal
                        self.reversal_count += 1
                        self.reversal_points.append((self.trials, self.get_current_contrast()))
                    self.direction = 1  # Increasing
                    self.current_index -= 1
                self.consecutive_errors = 0  # Reset after adjustment
        
        self.last_response_correct = correct
        
        return {
            "old_index": old_index,
            "new_index": self.current_index,
            "old_direction": old_direction,
            "new_direction": self.direction,
            "reversal": old_direction is not None and old_direction != self.direction,
            "reversal_count": self.reversal_count
        }
    
    def is_complete(self):
        """Check if staircase is complete (reached reversal threshold)"""
        return (self.reversal_count >= N_REVERSALS_CONTRAST and 
                self.trials >= MIN_TRIALS_PER_STAIRCASE)
    
    def get_threshold(self):
        """Calculate threshold as mean of last N reversal points"""
        if len(self.reversal_points) >= N_REVERSALS_CONTRAST:
            # Get contrast values from the last N_REVERSALS_CONTRAST reversal points
            last_reversals = [point[1] for point in self.reversal_points[-N_REVERSALS_CONTRAST:]]
            return np.mean(last_reversals)
        else:
            # Not enough reversal points, return current value
            return self.get_current_contrast()

# --- Experiment Setup ---

# 1. Get Participant Details
exp_info = {
    'Participant ID': '',
    'Age': '',
    'Gender': ('Male', 'Female', 'Other', 'Prefer not to say'),
    'Viewing Distance (cm)': 100, 
}

dlg = gui.DlgFromDict(dictionary=exp_info, title='Experiment Setup', order=['Participant ID', 'Age', 'Gender', 'Viewing Distance (cm)'])
if not dlg.OK:
    core.quit()

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"{DATA_FOLDER}/participant_{exp_info['Participant ID']}_{timestamp}"

if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

exp = data.ExperimentHandler(name='RSVP_Adaptive', version='1.0',
                             extraInfo=exp_info, runtimeInfo=True,
                             originPath=__file__,
                             savePickle=True, saveWideText=True,
                             dataFileName=filename)

logFile = logging.LogFile(filename + '.log', level=logging.EXP)
logging.console.setLevel(logging.WARNING)

monitor_name = 'testMonitor'
mon = monitors.Monitor(monitor_name)
mon.setDistance(float(exp_info['Viewing Distance (cm)']))
mon.save()

# Setting background to mid-gray
background_color = 0
win = visual.Window(
    size=mon.getSizePix(),
    fullscr=True,
    screen=0,
    winType='pyglet',
    allowGUI=False,
    allowStencil=False,
    monitor=mon,
    color=background_color,
    colorSpace='rgb',
    blendMode='avg',
    useFBO=True,
    units='deg'
)

print("Measuring monitor refresh rate... (this may take a few seconds)")
actual_frame_rate = win.getActualFrameRate(nIdentical=10, nMaxFrames=100, nWarmUpFrames=10, threshold=1)
if actual_frame_rate is not None:
    exp_info['frameRate'] = actual_frame_rate
    frameDur = 1.0 / round(actual_frame_rate)
    print(f"Measured refresh rate: {actual_frame_rate:.2f} Hz (frame duration: {frameDur*1000:.2f} ms)")
else:
    exp_info['frameRate'] = 60.0
    frameDur = 1.0 / 60.0
    logging.warning("Could not measure frame rate, assuming 60Hz.")
    print("WARNING: Could not measure frame rate - assuming 60Hz.")

ITEM_DURATION_FRAMES = max(1, round(ITEM_DURATION_MS / (frameDur * 1000)))
PRACTICE_DURATION_FRAMES = max(1, round((ITEM_DURATION_MS / PRACTICE_SPEED_FACTOR) / (frameDur * 1000)))
print(f"Item duration: {ITEM_DURATION_FRAMES} frames ({ITEM_DURATION_FRAMES * frameDur * 1000:.2f} ms)")
print(f"Practice duration: {PRACTICE_DURATION_FRAMES} frames ({PRACTICE_DURATION_FRAMES * frameDur * 1000:.2f} ms)")

port = initialize_serial_port()

# --- Load LogMAR and Contrast Values ---
try:
    # Load LogMAR values from conditions.csv
    if os.path.exists('conditions.csv'):
        with open('conditions.csv', 'r') as f:
            reader = csv.DictReader(f)
            logmar_values = [row['logmar'] for row in reader]
        print(f"Loaded {len(logmar_values)} LogMAR values from conditions.csv")
    else:
        # Default LogMAR values if file doesn't exist
        logmar_values = ['1.0', '0.9', '0.8', '0.7', '0.6', '0.5', '0.4', '0.3', '0.2', '0.1', '0.0', '-0.1', '-0.2', '-0.3']
        print(f"Using {len(logmar_values)} default LogMAR values")
    
    # Load contrast values from contrast_conditions.csv
    if os.path.exists('contrast_conditions.csv'):
        with open('contrast_conditions.csv', 'r') as f:
            reader = csv.DictReader(f)
            contrast_values = [row['contrastPct'] for row in reader]
        print(f"Loaded {len(contrast_values)} contrast values from contrast_conditions.csv")
    else:
        # Default contrast values if file doesn't exist
        contrast_values = ['100', '90', '80', '70', '60', '50', '40', '30', '20', '10', '5', '2.5', '1.25']
        print(f"Using {len(contrast_values)} default contrast values")
except Exception as e:
    print(f"ERROR: Unable to load condition values: {e}")
    # Default values as fallback
    logmar_values = ['1.0', '0.9', '0.8', '0.7', '0.6', '0.5', '0.4', '0.3', '0.2', '0.1', '0.0', '-0.1', '-0.2', '-0.3']
    contrast_values = ['100', '90', '80', '70', '60', '50', '40', '30', '20', '10', '5', '2.5', '1.25']
    print(f"Using default values: {len(logmar_values)} LogMAR values and {len(contrast_values)} contrast values")

# --- Text Stimuli ---
welcome_text = visual.TextStim(win=win, text="Welcome to the experiment!\n\nPress SPACE or ENTER to continue.", height=1.0, wrapWidth=30, color=-1)
instruction_text = visual.TextStim(win=win, text=(
    "Instructions:\n\n"
    "You will see a rapid stream of items in the center of the screen.\n"
    "Each stream contains numbers and ONE letter.\n"
    "Your task is to identify the LETTER.\n\n"
    "The experiment will adapt to your performance.\n"
    "First, the size of the letters will change, then their contrast.\n\n"
    "First, there will be a short practice.\n\n"
    "Press SPACE or ENTER to start the practice."), height=0.8, wrapWidth=30, color=-1)
practice_instruction_text = visual.TextStim(win=win, text="Practice Run\n\nPress SPACE or ENTER to begin.", height=1.0, wrapWidth=30, color=-1)

left_eye_size_text = visual.TextStim(win=win, text="Left Eye - Size Adjustment Phase\n\nPlease cover your RIGHT eye now.\n\nYou will need to identify the letter in each trial.\n\nPress SPACE or ENTER to begin.", height=1.0, wrapWidth=30, color=-1)
right_eye_size_text = visual.TextStim(win=win, text="Right Eye - Size Adjustment Phase\n\nPlease cover your LEFT eye now.\n\nYou will need to identify the letter in each trial.\n\nPress SPACE or ENTER to begin.", height=1.0, wrapWidth=30, color=-1)

left_eye_contrast_text = visual.TextStim(win=win, text="Left Eye - Contrast Adjustment Phase\n\nKeep your RIGHT eye covered.\n\nThe size will stay fixed, but the contrast will change.\n\nPress SPACE or ENTER to begin.", height=1.0, wrapWidth=30, color=-1)
right_eye_contrast_text = visual.TextStim(win=win, text="Right Eye - Contrast Adjustment Phase\n\nKeep your LEFT eye covered.\n\nThe size will stay fixed, but the contrast will change.\n\nPress SPACE or ENTER to begin.", height=1.0, wrapWidth=30, color=-1)

switch_to_right_eye_text = visual.TextStim(win=win, text="Left Eye Testing Complete\n\nNow we'll switch to your RIGHT eye.\n\nPlease take a short break if needed.\n\nPress SPACE or ENTER when you're ready to continue.", height=1.0, wrapWidth=30, color=-1)
fixation_cross = visual.TextStim(win=win, text='+', height=2, color=-1)
rsvp_stim = visual.TextStim(win=win, text='', height=1.0, color=-1)
response_prompt_text = visual.TextStim(win=win, text="Which letter did you see?\n(Type the letter and press ENTER)", height=1.0, wrapWidth=30, color=-1)
typed_response_text = visual.TextStim(win=win, text="", height=1.5, pos=(0, -3), color=-1)
next_trial_text = visual.TextStim(win=win, text="Press SPACE to start the next trial.", height=1.0, wrapWidth=30, color=-1)
goodbye_text = visual.TextStim(win=win, text="Thank you for participating!\n\nThe experiment is now complete.", height=1.0, wrapWidth=30, color=-1)

kb = event.BuilderKeyResponse()

def show_message(text_stim, wait_keys=['space', 'return', 'enter']):
    """Displays a TextStim and waits for a key press."""
    text_stim.draw()
    win.flip()
    event.waitKeys(keyList=wait_keys)
    win.flip()

def collect_response(prompt_stim, typed_stim):
    """Collects a typed response until Enter is pressed."""
    response_str = ""
    typed_stim.text = ""
    prompt_stim.draw()
    typed_stim.draw()
    win.flip()

    while True:
        keys = event.getKeys(keyList=['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
                                       'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
                                       'backspace', 'return', 'enter', 'escape'])
        if not keys:
            prompt_stim.draw()
            typed_stim.draw()
            win.flip()
            continue

        key = keys[0]

        if key in ['escape']:
            print("User aborted experiment.")
            core.quit()
        elif key in ['return', 'enter']:
            if response_str:
                break
        elif key == 'backspace':
            response_str = response_str[:-1]
            typed_stim.text = response_str.upper()
        else:
            response_str += key
            typed_stim.text = response_str.upper()

        prompt_stim.draw()
        typed_stim.draw()
        win.flip()

    win.flip()
    return response_str.upper()

def run_rsvp_trial(win, stim_size_deg, stim_color=-1, item_duration_frames=ITEM_DURATION_FRAMES):
    """
    Run a single RSVP trial
    
    Args:
        win: PsychoPy window
        stim_size_deg (float): Stimulus size in degrees
        stim_color: Stimulus color (-1 to 1 for grayscale)
        item_duration_frames (int): Duration of each item in frames
        
    Returns:
        tuple: (target_letter, target_position, stream, response, accuracy)
    """
    target_letter = random.choice(TARGET_LETTERS)
    target_position = random.randint(TARGET_POS_MIN, TARGET_POS_MAX)

    stream = []
    for i in range(N_STREAM_ITEMS):
        if i == target_position:
            stream.append(target_letter)
        else:
            distractor = random.choice(DISTRACTORS)
            while stream and distractor == stream[-1]:
                distractor = random.choice(DISTRACTORS)
            stream.append(distractor)

    fixation_cross.draw()
    win.flip()
    core.wait(FIXATION_PRE_STREAM_DUR)

    for i, item in enumerate(stream):
        rsvp_stim.setText(item)
        rsvp_stim.setHeight(stim_size_deg)
        rsvp_stim.setColor(stim_color)
        
        for frame in range(item_duration_frames):
            if i == 0 and frame == 0:
                send_trigger(port, TRIGGER_STREAM_START)
                logging.exp(f"RSVP Stream Start - Item: {item}")
            
            if i == target_position and frame == 0:
                send_trigger(port, TRIGGER_TARGET_ONSET)
                logging.exp(f"Target Letter Onset - Letter: {item}")
            
            if frame == 0:
                # Send item-specific trigger for each stimulus
                send_trigger(port, TRIGGER_MAP[item])
                logging.exp(f"Stimulus Onset - Item: {item}, Trigger: {TRIGGER_MAP[item]}")
            
            rsvp_stim.draw()
            win.flip()

    fixation_cross.draw()
    
    send_trigger(port, TRIGGER_STREAM_END)
    logging.exp("RSVP Stream End - Start of end fixation")
    
    win.flip()
    core.wait(FIXATION_POST_STREAM_RESPONSE_DUR)
    win.flip()

    response = collect_response(response_prompt_text, typed_response_text)
    accuracy = 1 if response == target_letter else 0

    return target_letter, target_position, stream, response, accuracy

def run_practice_trials():
    """Run practice trials"""
    show_message(practice_instruction_text)
    
    # Use a large size and high contrast for practice
    practice_size_deg = logmar_to_degrees(float(logmar_values[min(3, len(logmar_values)-1)]))
    practice_color = -1  # Full contrast
    
    for trial in range(N_PRACTICE_TRIALS):
        target, pos, stream, resp, acc = run_rsvp_trial(
            win, 
            stim_size_deg=practice_size_deg,
            stim_color=practice_color,
            item_duration_frames=PRACTICE_DURATION_FRAMES
        )
        
        exp.addData('block_type', 'practice')
        exp.addData('trial_num', trial + 1)
        exp.addData('target_letter', target)
        exp.addData('target_position', pos)
        exp.addData('stim_size_deg', practice_size_deg)
        exp.addData('stim_contrast', 100)  # Full contrast
        exp.addData('response', resp)
        exp.addData('accuracy', acc)
        exp.nextEntry()
        
        if trial < N_PRACTICE_TRIALS - 1:
            show_message(next_trial_text, wait_keys=['space'])

def run_size_staircase(eye):
    """
    Run the size staircase procedure
    
    Args:
        eye (str): 'left' or 'right'
        
    Returns:
        float: Threshold LogMAR value
    """
    if eye == 'left':
        show_message(left_eye_size_text)
        block_prefix = 'left_eye_size'
    else:
        show_message(right_eye_size_text)
        block_prefix = 'right_eye_size'
    
    staircase = SizeStaircase(logmar_values, starting_logmar=SIZE_LOGMAR_START)
    
    trial_num = 0
    max_trials = 100  # Safety limit
    
    print(f"\n--- Starting {eye.capitalize()} Eye Size Staircase ---")
    
    while not staircase.is_complete() and trial_num < max_trials:
        trial_num += 1
        current_size_deg = staircase.get_current_size_deg()
        current_logmar = staircase.get_current_logmar()
        
        print(f"Trial {trial_num}: Size = {current_size_deg:.4f} deg (LogMAR {current_logmar:.2f})")
        
        target, pos, stream, resp, acc = run_rsvp_trial(
            win,
            stim_size_deg=current_size_deg,
            stim_color=-1,  # Full contrast during size staircase
            item_duration_frames=ITEM_DURATION_FRAMES
        )
        
        update_info = staircase.record_response(acc == 1)
        
        # Log data
        exp.addData('block_type', block_prefix)
        exp.addData('trial_num', trial_num)
        exp.addData('target_letter', target)
        exp.addData('target_position', pos)
        exp.addData('stim_logmar', current_logmar)
        exp.addData('stim_size_deg', current_size_deg)
        exp.addData('stim_contrast', 100)  # Full contrast
        exp.addData('response', resp)
        exp.addData('accuracy', acc)
        exp.addData('direction', update_info['new_direction'])
        exp.addData('reversal', update_info['reversal'])
        exp.addData('reversal_count', update_info['reversal_count'])
        exp.nextEntry()
        
        if update_info['reversal']:
            print(f"  REVERSAL {update_info['reversal_count']}: Old dir={update_info['old_direction']}, New dir={update_info['new_direction']}")
        
        if staircase.is_complete():
            print(f"Staircase complete after {trial_num} trials with {staircase.reversal_count} reversals")
            threshold = staircase.get_threshold()
            print(f"Size threshold LogMAR: {threshold:.2f}")
            break
            
        # Only show "next trial" if not the last one
        if not staircase.is_complete() and trial_num < max_trials - 1:
            show_message(next_trial_text, wait_keys=['space'])
    
    return staircase.get_threshold()

def run_contrast_staircase(eye, size_threshold_logmar):
    """
    Run the contrast staircase procedure
    
    Args:
        eye (str): 'left' or 'right'
        size_threshold_logmar (float): Size threshold from size staircase
        
    Returns:
        float: Threshold contrast value
    """
    if eye == 'left':
        show_message(left_eye_contrast_text)
        block_prefix = 'left_eye_contrast'
    else:
        show_message(right_eye_contrast_text)
        block_prefix = 'right_eye_contrast'
    
    # Convert LogMAR to degrees
    size_threshold_deg = logmar_to_degrees(size_threshold_logmar)
    
    staircase = ContrastStaircase(contrast_values, starting_contrast=CONTRAST_START_PCT)
    
    trial_num = 0
    max_trials = 100  # Safety limit
    
    print(f"\n--- Starting {eye.capitalize()} Eye Contrast Staircase ---")
    print(f"Using fixed size: LogMAR {size_threshold_logmar:.2f} ({size_threshold_deg:.4f} deg)")
    
    while not staircase.is_complete() and trial_num < max_trials:
        trial_num += 1
        current_contrast = staircase.get_current_contrast()
        current_color = staircase.get_current_color_value(background_color)
        
        print(f"Trial {trial_num}: Contrast = {current_contrast:.2f}%")
        
        target, pos, stream, resp, acc = run_rsvp_trial(
            win,
            stim_size_deg=size_threshold_deg,
            stim_color=current_color,
            item_duration_frames=ITEM_DURATION_FRAMES
        )
        
        update_info = staircase.record_response(acc == 1)
        
        # Log data
        exp.addData('block_type', block_prefix)
        exp.addData('trial_num', trial_num)
        exp.addData('target_letter', target)
        exp.addData('target_position', pos)
        exp.addData('stim_logmar', size_threshold_logmar)
        exp.addData('stim_size_deg', size_threshold_deg)
        exp.addData('stim_contrast', current_contrast)
        exp.addData('response', resp)
        exp.addData('accuracy', acc)
        exp.addData('direction', update_info['new_direction'])
        exp.addData('reversal', update_info['reversal'])
        exp.addData('reversal_count', update_info['reversal_count'])
        exp.nextEntry()
        
        if update_info['reversal']:
            print(f"  REVERSAL {update_info['reversal_count']}: Old dir={update_info['old_direction']}, New dir={update_info['new_direction']}")
        
        if staircase.is_complete():
            print(f"Staircase complete after {trial_num} trials with {staircase.reversal_count} reversals")
            threshold = staircase.get_threshold()
            print(f"Contrast threshold: {threshold:.2f}%")
            break
            
        # Only show "next trial" if not the last one
        if not staircase.is_complete() and trial_num < max_trials - 1:
            show_message(next_trial_text, wait_keys=['space'])
    
    return staircase.get_threshold()

# --- Run Experiment ---
# Welcome and instructions
show_message(welcome_text)
show_message(instruction_text)

# Practice trials
run_practice_trials()

# Main experiment for each eye
results = {}
for eye in ['left', 'right']:
    # Size staircase
    size_threshold = run_size_staircase(eye)
    results[f'{eye}_size_threshold'] = size_threshold
    
    # Contrast staircase (using size threshold)
    contrast_threshold = run_contrast_staircase(eye, size_threshold)
    results[f'{eye}_contrast_threshold'] = contrast_threshold
    
    # If this is the left eye, show message to switch to right eye
    if eye == 'left':
        show_message(switch_to_right_eye_text)

# Display final results
results_text = (
    f"Results Summary:\n\n"
    f"Left Eye:\n"
    f"  Size Threshold (LogMAR): {results['left_size_threshold']:.2f}\n"
    f"  Contrast Threshold: {results['left_contrast_threshold']:.2f}%\n\n"
    f"Right Eye:\n"
    f"  Size Threshold (LogMAR): {results['right_size_threshold']:.2f}\n"
    f"  Contrast Threshold: {results['right_contrast_threshold']:.2f}%"
)

final_results_text = visual.TextStim(win=win, text=results_text, height=0.8, wrapWidth=30, color=-1)
final_results_text.draw()
win.flip()
core.wait(10.0)  # Display results for 10 seconds

goodbye_text.draw()
win.flip()
core.wait(3.0)

# Save results to a separate summary file
with open(f"{filename}_summary.csv", 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['measure', 'value'])
    for key, value in results.items():
        writer.writerow([key, value])

exp.saveAsWideText(filename + '.csv')
exp.saveAsPickle(filename + '.psydat')
logging.flush()

if port is not None and SERIAL_PORT_AVAILABLE:
    port.write(bytes([0]))
    logging.exp("Serial port reset at experiment end")

win.close()
core.quit()