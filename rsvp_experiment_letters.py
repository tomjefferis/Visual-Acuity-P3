"""
PsychoPy script for an RSVP (Rapid Serial Visual Presentation) experiment.
Presents streams of letters (target) and numbers (distractors) at varying sizes.
Collects target identification responses for some blocks.
Runs separate blocks for left and right eyes.
"""

from psychopy import core, visual, gui, data, event, logging, monitors
import random
import os
import csv
from datetime import datetime
import serial

# --- Constants ---
TARGET_LETTERS = ['C', 'D', 'H', 'K', 'N', 'F', 'R', 'S', 'V', 'Z']
DISTRACTORS = [str(i) for i in range(1, 10)]
N_STREAM_ITEMS = 16
TARGET_POS_MIN = 3 
TARGET_POS_MAX = 8 
FIXATION_PRE_STREAM_DUR = 0.700 
FIXATION_POST_STREAM_RESPONSE_DUR = 0.5 
FIXATION_POST_STREAM_NO_RESPONSE_DUR = 1.000 

# Serial port configuration
SERIAL_PORT_AVAILABLE = True
SERIAL_PORT_NAME = '/dev/cu.usbmodem11301'  # Testing for now 
SERIAL_BAUD_RATE = 115200

# --- Item Duration ---
ITEM_DURATION_MS = 100  # Target duration in milliseconds
PRACTICE_SPEED_FACTOR = 1  # Practice speed 0-1

N_TRIALS_PER_SIZE = 16
N_PRACTICE_TRIALS = 2 
CONDITIONS_FILE = 'conditions.csv'
DATA_FOLDER = 'data' # Folder to save data files

# --- Trigger Values ---
# New trigger codes to avoid conflicts with stimulus-specific triggers
TRIGGER_STREAM_START = 101    # First item onset
TRIGGER_TARGET_ONSET = 102    # Target presentation 
TRIGGER_STREAM_END = 103      # End of stream (post-stream fixation onset)

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

def initialize_serial_port():
    """Initialize the serial port for sending triggers to BioSemi/LabJack."""
    if SERIAL_PORT_AVAILABLE:
        try:
            ser = serial.Serial(
                port=SERIAL_PORT_NAME,
                baudrate=SERIAL_BAUD_RATE
            )
            ser.write(bytes([0]))
            print(f"Serial port initialized at {SERIAL_PORT_NAME}, baudrate {SERIAL_BAUD_RATE}")
            return ser
        except Exception as e:
            print(f"WARNING: Failed to initialize serial port: {e}")
            print("EEG triggers will be simulated.")
            return None
    return None


def send_trigger(port, trigger_value):
    """Send a trigger value to the serial port."""
    if port is not None and SERIAL_PORT_AVAILABLE:
        port.write(bytes([trigger_value]))
        logging.exp(f"TRIGGER: Sent value {trigger_value} to serial port")
        port.write(bytes([0]))  # Reset trigger, not sure if needed
    else:
        logging.exp(f"TRIGGER: Simulated sending value {trigger_value} to serial port")


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

# --- Experiment Setup ---
exp_info = {
    'Participant ID': '',
    'Age': '',
    'Gender': ('Male', 'Female', 'Other', 'Prefer not to say'),
    'Viewing Distance (cm)': 57, 
}

dlg = gui.DlgFromDict(dictionary=exp_info, title='Experiment Setup', order=['Participant ID', 'Age', 'Gender', 'Viewing Distance (cm)'])
if not dlg.OK:
    core.quit()

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"{DATA_FOLDER}/participant_{exp_info['Participant ID']}_{timestamp}"

if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

exp = data.ExperimentHandler(name='RSVP_Size', version='1.0',
                             extraInfo=exp_info, runtimeInfo=True,
                             originPath=__file__,
                             savePickle=True, saveWideText=True,
                             dataFileName=filename)

logFile = logging.LogFile(filename + '.log', level=logging.EXP)
logging.console.setLevel(logging.WARNING)

# Monitor configuration
monitor_name = 'testMonitor'
mon = monitors.Monitor(monitor_name)
mon.setDistance(float(exp_info['Viewing Distance (cm)']))
mon.save()

win = visual.Window(
    size=mon.getSizePix(),
    fullscr=False,
    screen=0,
    winType='pyglet',
    allowGUI=True,
    allowStencil=True,
    monitor=mon,
    color='grey',
    colorSpace='rgb',
    blendMode='avg',
    useFBO=True,
    units='deg'
)

actual_frame_rate = win.getActualFrameRate(nIdentical=10, nMaxFrames=100, nWarmUpFrames=10, threshold=1)
if actual_frame_rate is not None:
    exp_info['frameRate'] = actual_frame_rate
    frameDur = 1.0 / round(actual_frame_rate)
    print(f"Measured refresh rate: {actual_frame_rate:.2f} Hz (frame duration: {frameDur*1000:.2f} ms)")
else:
    exp_info['frameRate'] = 60.0
    frameDur = 1.0 / 60.0
    logging.warning("Could not measure frame rate, assuming 60Hz.")

ITEM_DURATION_FRAMES = max(1, round(ITEM_DURATION_MS / (frameDur * 1000)))
PRACTICE_DURATION_FRAMES = max(1, round((ITEM_DURATION_MS / PRACTICE_SPEED_FACTOR) / (frameDur * 1000)))
print(f"Item duration: {ITEM_DURATION_FRAMES} frames ({ITEM_DURATION_FRAMES * frameDur * 1000:.2f} ms)")
print(f"Practice duration: {PRACTICE_DURATION_FRAMES} frames ({PRACTICE_DURATION_FRAMES * frameDur * 1000:.2f} ms)")

port = initialize_serial_port()


snellen_font = 'Snellen'  # Font for stimuli


welcome_text = visual.TextStim(win=win, text="Welcome to the experiment!\n\nPress SPACE or ENTER to continue.", height=1.0)
instruction_text = visual.TextStim(win=win, text=(
    "Instructions:\n\n"
    "You will see a rapid stream of items in the center of the screen.\n"
    "Each stream contains numbers and ONE letter.\n"
    "Your task is to identify the LETTER.\n\n"
    "First, there will be a short practice.\n\n"
    "Press SPACE or ENTER to start the practice."), height=0.8)
practice_instruction_text = visual.TextStim(win=win, text="Practice Run\n\nPress SPACE or ENTER to begin.", height=1.0)
left_eye_instruction_text = visual.TextStim(win=win, text="Left Eye Block - Part 1\n\nPlease cover your RIGHT eye now.\n\nYou will need to identify the letter in each trial.\n\nPress SPACE or ENTER to begin.", height=1.0)
right_eye_instruction_text = visual.TextStim(win=win, text="Right Eye Block - Part 1\n\nPlease cover your LEFT eye now.\n\nYou will need to identify the letter in each trial.\n\nPress SPACE or ENTER to begin.", height=1.0)
left_eye_no_response_text = visual.TextStim(win=win, text="Left Eye Block - Part 2\n\nKeep your RIGHT eye covered.\n\nIn this part, you do NOT need to respond.\nSimply watch the streams carefully.\n\nPress SPACE or ENTER to begin.", height=1.0)
right_eye_no_response_text = visual.TextStim(win=win, text="Right Eye Block - Part 2\n\nKeep your LEFT eye covered.\n\nIn this part, you do NOT need to respond.\nSimply watch the streams carefully.\n\nPress SPACE or ENTER to begin.", height=1.0)
switch_to_right_eye_text = visual.TextStim(win=win, text="Left Eye Block Complete\n\nNow we'll switch to your RIGHT eye.\n\nPlease take a short break if needed.\n\nPress SPACE or ENTER when you're ready to continue.", height=1.0)
fixation_cross = visual.TextStim(win=win, text='+', height=1, font=snellen_font)
response_prompt_text = visual.TextStim(win=win, text="Which letter did you see?\n(Type the letter and press ENTER)", height=1.0)
typed_response_text = visual.TextStim(win=win, text="", height=1.5, pos=(0, -3))
next_trial_text = visual.TextStim(win=win, text="Press SPACE to start the next trial.", height=1.0)
goodbye_text = visual.TextStim(win=win, text="Thank you for participating!\n\nThe experiment is now complete.", height=1.0)


rsvp_stim = visual.TextStim(win=win, text='', height=1.0, font=snellen_font)

kb = event.BuilderKeyResponse()


trial_conditions = data.importConditions(CONDITIONS_FILE)

min_size = float('inf')
max_size = float('-inf')

for condition in trial_conditions:
    if 'logmar' in condition:
        logmar_value = float(condition['logmar'])
        condition['stimSizeDeg'] = logmar_to_degrees(logmar_value)
        
        min_size = min(min_size, condition['stimSizeDeg'])
        max_size = max(max_size, condition['stimSizeDeg'])
        
        print(f"Converting LogMAR {logmar_value} to {condition['stimSizeDeg']} degrees")
    elif 'stimSizeDeg' not in condition:
        raise ValueError("Neither 'logmar' nor 'stimSizeDeg' found in conditions file")

print(f"Size range: {min_size} to {max_size} degrees of visual angle")

trial_conditions = sorted(trial_conditions, key=lambda x: x['stimSizeDeg'], reverse=True)

expanded_trial_list = []
for condition in trial_conditions:
    for _ in range(N_TRIALS_PER_SIZE):
        expanded_trial_list.append(condition.copy())

n_sizes = len(trial_conditions)
n_total_trials_per_block = n_sizes * N_TRIALS_PER_SIZE
print(f"Loaded {n_sizes} stimulus sizes from {CONDITIONS_FILE}.")
print(f"Total trials per main block part: {n_total_trials_per_block}")

practice_trials_list = [trial_conditions[0]] * N_PRACTICE_TRIALS
practice_handler = data.TrialHandler(nReps=1, method='random',
                                     originPath=-1,
                                     trialList=practice_trials_list,
                                     name='practice')
exp.addLoop(practice_handler)

trials_response = data.TrialHandler(nReps=1, method='sequential',
                                   originPath=-1,
                                   trialList=expanded_trial_list,
                                   name='trials_response')

trials_no_response = data.TrialHandler(nReps=1, method='sequential',
                                      originPath=-1,
                                      trialList=expanded_trial_list,
                                      name='trials_no_response')

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

def run_rsvp_trial(win, stim_size_deg, item_duration_frames, require_response=True, end_fix_duration=FIXATION_POST_STREAM_RESPONSE_DUR):
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
        rsvp_stim.height = stim_size_deg
        
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
    core.wait(end_fix_duration)
    win.flip()

    response = None
    accuracy = None
    if require_response:
        response = collect_response(response_prompt_text, typed_response_text)
        accuracy = 1 if response == target_letter else 0
    else:
        response = 'N/A'
        accuracy = 'N/A'

    return target_letter, target_position, stream, response, accuracy

show_message(welcome_text)

show_message(instruction_text)

show_message(practice_instruction_text)
current_trial_global = 0
for trial_num_practice, practice_trial_data in enumerate(practice_handler):
    current_trial_global += 1
    stim_size = practice_trial_data['stimSizeDeg']
    
    target, pos, stream_items, resp, acc = run_rsvp_trial(win,
                                             stim_size_deg=stim_size,
                                             item_duration_frames=PRACTICE_DURATION_FRAMES,
                                             require_response=True,
                                             end_fix_duration=FIXATION_POST_STREAM_RESPONSE_DUR)

    practice_handler.addData('block_type', 'practice')
    practice_handler.addData('trial_num_block', trial_num_practice + 1)
    practice_handler.addData('trial_num_global', current_trial_global)
    practice_handler.addData('target_letter', target)
    practice_handler.addData('target_position', pos)
    practice_handler.addData('stim_size_deg', stim_size)
    practice_handler.addData('response', resp)
    practice_handler.addData('accuracy', acc)
    exp.nextEntry()

    if trial_num_practice < N_PRACTICE_TRIALS - 1:
        show_message(next_trial_text, wait_keys=['space'])

for eye in ['left', 'right']:

    if eye == 'left':
        show_message(left_eye_instruction_text)
        block_prefix = 'left_eye'
    else:
        show_message(right_eye_instruction_text)
        block_prefix = 'right_eye'

    trials_response = data.TrialHandler(nReps=1, method='sequential',
                                        originPath=-1,
                                        trialList=expanded_trial_list,
                                        name='trials_response')
    
    trials_no_response = data.TrialHandler(nReps=1, method='sequential',
                                          originPath=-1,
                                          trialList=expanded_trial_list,
                                          name='trials_no_response')

    print(f"\n--- Starting {eye.capitalize()} Eye Block - Part 1 (Response) ---")
    exp.addLoop(trials_response)
    for trial_num_block, trial_data in enumerate(trials_response):
        current_trial_global += 1
        stim_size = trial_data['stimSizeDeg']

        target, pos, stream_items, resp, acc = run_rsvp_trial(
            win,
            stim_size_deg=stim_size,
            item_duration_frames=ITEM_DURATION_FRAMES,
            require_response=True,
            end_fix_duration=FIXATION_POST_STREAM_RESPONSE_DUR
        )

        trials_response.addData('block_type', f'{block_prefix}_response')
        trials_response.addData('trial_num_block', trial_num_block + 1)
        trials_response.addData('trial_num_global', current_trial_global)
        trials_response.addData('target_letter', target)
        trials_response.addData('target_position', pos)
        trials_response.addData('response', resp)
        trials_response.addData('accuracy', acc)
        exp.nextEntry()

        if trial_num_block < n_total_trials_per_block - 1:
            show_message(next_trial_text, wait_keys=['space'])
        else:
            core.wait(1.0)

    if eye == 'left':
        show_message(left_eye_no_response_text)
    else:
        show_message(right_eye_no_response_text)

    print(f"\n--- Starting {eye.capitalize()} Eye Block - Part 2 (No Response) ---")
    exp.addLoop(trials_no_response)
    for trial_num_block, trial_data in enumerate(trials_no_response):
        current_trial_global += 1
        stim_size = trial_data['stimSizeDeg']

        target, pos, stream_items, resp, acc = run_rsvp_trial(
            win,
            stim_size_deg=stim_size,
            item_duration_frames=ITEM_DURATION_FRAMES,
            require_response=False,
            end_fix_duration=FIXATION_POST_STREAM_NO_RESPONSE_DUR
        )

        trials_no_response.addData('block_type', f'{block_prefix}_no_response')
        trials_no_response.addData('trial_num_block', trial_num_block + 1)
        trials_no_response.addData('trial_num_global', current_trial_global)
        trials_no_response.addData('target_letter', target)
        trials_no_response.addData('target_position', pos)
        trials_no_response.addData('response', resp)
        trials_no_response.addData('accuracy', acc)
        exp.nextEntry()

        is_last_overall_trial = (eye == 'right' and trial_num_block == n_total_trials_per_block - 1)
        if not is_last_overall_trial:
             show_message(next_trial_text, wait_keys=['space'])

    if eye == 'left':
        show_message(switch_to_right_eye_text)

goodbye_text.draw()
win.flip()
core.wait(3.0)

exp.saveAsWideText(filename + '.csv')
exp.saveAsPickle(filename + '.psydat')
logging.flush()

if port is not None and SERIAL_PORT_AVAILABLE:
    port.write(bytes([0]))
    logging.exp("Serial port reset at experiment end")

win.close()
core.quit()