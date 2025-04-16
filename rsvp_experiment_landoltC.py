"""
PsychoPy script for an RSVP (Rapid Serial Visual Presentation) experiment.
Presents streams of Landolt C target and distractors at varying sizes.
The target appears in 50% of streams, and participants respond whether they saw it.
Runs separate blocks for left and right eyes.
"""

from psychopy import core, visual, gui, data, event, monitors
import random
import os
import csv
from datetime import datetime

# EEG triggers
try:
    from psychopy import parallel
    PARALLEL_PORT_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    PARALLEL_PORT_AVAILABLE = False
    print("WARNING: Parallel port module not available. EEG triggers will be simulated.")

# --- Constants ---
# Target frequency - percentage of trials that should contain the target (0-100)
TARGET_PRESENT_PERCENT = 100 
N_STREAM_ITEMS = 16
TARGET_POS_MIN = 3 
TARGET_POS_MAX = 8 
FIXATION_PRE_STREAM_DUR = 0.700 
FIXATION_POST_STREAM_RESPONSE_DUR = 0.5 
FIXATION_POST_STREAM_NO_RESPONSE_DUR = 1.000 

# --- Trigger Values ---
TRIGGER_STREAM_START = 1    # First item onset
TRIGGER_TARGET_ONSET = 2    # Target presentation 
TRIGGER_STREAM_END = 3      # End of stream (post-stream fixation onset)
TRIGGER_DURATION_MS = 10    # Duration to keep trigger on (in ms)

# Default port address for parallel port
PARALLEL_PORT_ADDRESS = 0x378  # Standard address, may need adjustment for the system

# --- Item Duration ---
# Will determine item duration in frames based on measured refresh rate
ITEM_DURATION_MS = 130  # Target duration in milliseconds
PRACTICE_SPEED_FACTOR = 0.75  # Practice speed

N_TRIALS_PER_SIZE = 1
N_PRACTICE_TRIALS = 2 
CONDITIONS_FILE = 'conditions.csv'
DATA_FOLDER = 'data' # Folder to save data files

# --- Initialize parallel port ---
def initialize_parallel_port():
    """Initialize the parallel port for sending triggers if available."""
    if (PARALLEL_PORT_AVAILABLE):
        try:
            port = parallel.ParallelPort(address=PARALLEL_PORT_ADDRESS)
            port.setData(0)
            print(f"Parallel port initialized at address {PARALLEL_PORT_ADDRESS}")
            return port
        except Exception as e:
            print(f"WARNING: Failed to initialize parallel port: {e}")
            print("EEG triggers will be simulated.")
            return None
    return None

# --- Send trigger function ---
def send_trigger(port, trigger_value):
    """Send a trigger value to the parallel port."""
    if port is not None and PARALLEL_PORT_AVAILABLE:
        port.setData(trigger_value)
        core.wait(TRIGGER_DURATION_MS/1000.0)
        port.setData(0)
        
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
    # Convert LogMAR to arcmin
    size_arcmin = 5 * (10 ** logmar_value)
    # Convert arcmin to degrees
    size_degrees = size_arcmin / 60.0
    
    return size_degrees

# --- Experiment Setup ---

# Participant information
exp_info = {
    'Participant ID': '',
    'Age': '',
    'Gender': ('Male', 'Female', 'Other', 'Prefer not to say'),
    'Viewing Distance (cm)': 100,
}

dlg = gui.DlgFromDict(dictionary=exp_info, title='Experiment Setup', order=['Participant ID', 'Age', 'Gender', 'Viewing Distance (cm)'])
if not dlg.OK:
    core.quit()

# Create filename
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"{DATA_FOLDER}/participant_{exp_info['Participant ID']}_{timestamp}"

# Ensure data folder exists
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# Setup ExperimentHandler 
exp = data.ExperimentHandler(name='RSVP_LandoltC', version='1.0',
                             extraInfo=exp_info, runtimeInfo=True,
                             originPath=__file__, # Saves the script path
                             savePickle=True, saveWideText=True, # Save in both formats
                             dataFileName=filename)


# --- Monitor and Window Setup ---
monitor_name = 'testMonitor' # IMPORTANT: Replace 'testMonitor' with the name of the calibrated monitor profile in PsychoPy Monitor Center
mon = monitors.Monitor(monitor_name)
mon.setDistance(float(exp_info['Viewing Distance (cm)']))
mon.save()

# Create the window - Use 'deg' for size units based on monitor calibration
win = visual.Window(
    size=mon.getSizePix(), # Use monitor's pixel size
    fullscr=False, 
    screen=0, 
    winType='pyglet',
    allowGUI=False,
    allowStencil=False,
    monitor=mon, 
    color='grey',
    colorSpace='rgb',
    blendMode='avg',
    useFBO=True,
    units='deg' 
)

# getting frame rate
actual_frame_rate = win.getActualFrameRate(nIdentical=10, nMaxFrames=100, nWarmUpFrames=10, threshold=1)
if actual_frame_rate is not None:
    exp_info['frameRate'] = actual_frame_rate
    frameDur = 1.0 / round(actual_frame_rate)
else:
    exp_info['frameRate'] = 60.0
    frameDur = 1.0 / 60.0

# Calculate frame-based durations based on measured refresh rate ~= 6 frames for 60Hz
ITEM_DURATION_FRAMES = max(1, round(ITEM_DURATION_MS / (frameDur * 1000)))
PRACTICE_DURATION_FRAMES = max(1, round((ITEM_DURATION_MS / PRACTICE_SPEED_FACTOR) / (frameDur * 1000)))

port = initialize_parallel_port()

# --- Load Stimuli Images ---
target_image = visual.ImageStim(win=win, image='images/target.png', units='deg')
distractor_images = []
for i in range(1, 9):
    img_path = f"images/{i}.png"
    if os.path.exists(img_path):
        img = visual.ImageStim(win=win, image=img_path, units='deg')
        distractor_images.append(img)

# --- Stimuli Setup ---
welcome_text = visual.TextStim(win=win, text="Welcome to the experiment!\n\nPress SPACE or ENTER to continue.", height=1.0, wrapWidth=30)

# Create instruction screens
instruction_text = visual.TextStim(win=win, text=(
    "Instructions:\n\n"
    "You will see a rapid stream of images in the center of the screen.\n"
    "You will be looking for the image in the target orientation.\n"
    "Some streams will contain a the target orientation.\n"
    "Your task is to determine if the target was present in the stream.\n\n"
    "On the next screen, you will see the target image.\n\n"
    "Press SPACE or ENTER to continue."), height=0.8, pos=(0, 0), wrapWidth=30)

# Second instruction screen showing the target image
target_display_text = visual.TextStim(win=win, text="This is the target orientation.\n\nPress SPACE or ENTER to start the practice.", 
                                     height=0.8, pos=(0, 3), wrapWidth=30)

instruction_target_example = visual.ImageStim(win=win, image='images/target.png', units='deg', size=(3, 3), pos=(0, -2))

# instruction text elements
practice_instruction_text = visual.TextStim(win=win, text="Practice Run (Slightly Slower)\n\nPress SPACE or ENTER to begin.", height=1.0, wrapWidth=30)
left_eye_instruction_text = visual.TextStim(win=win, text="Left Eye Block - Part 1 (With Response)\n\nPlease cover your RIGHT eye now.\n\nYou will need to respond whether you saw the target in each trial.\n\nPress SPACE or ENTER to begin.", height=1.0, wrapWidth=30)
right_eye_instruction_text = visual.TextStim(win=win, text="Right Eye Block - Part 1 (With Response)\n\nPlease cover your LEFT eye now.\n\nYou will need to respond whether you saw the target in each trial.\n\nPress SPACE or ENTER to begin.", height=1.0, wrapWidth=30)
left_eye_no_response_text = visual.TextStim(win=win, text="Left Eye Block - Part 2 (No Response)\n\nKeep your RIGHT eye covered.\n\nIn this part, you do NOT need to respond.\nSimply watch the streams carefully.\n\nPress SPACE or ENTER to begin.", height=1.0, wrapWidth=30)
right_eye_no_response_text = visual.TextStim(win=win, text="Right Eye Block - Part 2 (No Response)\n\nKeep your LEFT eye covered.\n\nIn this part, you do NOT need to respond.\nSimply watch the streams carefully.\n\nPress SPACE or ENTER to begin.", height=1.0, wrapWidth=30)
switch_to_right_eye_text = visual.TextStim(win=win, text="Left Eye Block Complete\n\nNow we'll switch to your RIGHT eye.\n\nPlease take a short break if needed.\n\nPress SPACE or ENTER when you're ready to continue.", height=1.0, wrapWidth=30)
fixation_cross = visual.TextStim(win=win, text='+', height=2, color='black')
response_prompt_text = visual.TextStim(win=win, text="Did you see this orientation in the stream?\n\nPress 'Y' for YES or 'N' for NO", height=1.0, wrapWidth=30, pos=(0, 3))
response_target_example = visual.ImageStim(win=win, image='images/target.png', units='deg', size=(3, 3), pos=(0, -2))
next_trial_text = visual.TextStim(win=win, text="Press SPACE to start the next trial.", height=1.0, wrapWidth=30)
goodbye_text = visual.TextStim(win=win, text="Thank you for participating!\n\nThe experiment is now complete.", height=1.0, wrapWidth=30)

rsvp_stim = visual.ImageStim(win=win, units='deg')


kb = event.BuilderKeyResponse()

# --- Load Conditions ---
trial_conditions = data.importConditions(CONDITIONS_FILE)

# Convert LogMAR values to degrees of visual angle
min_size = float('inf')
max_size = float('-inf')

for condition in trial_conditions:
    if 'logmar' in condition:
        # Convert logmar to degrees and add/update the stimSizeDeg field
        logmar_value = float(condition['logmar'])
        condition['stimSizeDeg'] = logmar_to_degrees(logmar_value)
        
        # Keep track of min/max sizes for debugging
        min_size = min(min_size, condition['stimSizeDeg'])
        max_size = max(max_size, condition['stimSizeDeg'])
        
        print(f"Converting LogMAR {logmar_value} to {condition['stimSizeDeg']} degrees")
    elif 'stimSizeDeg' not in condition:
        raise ValueError("Neither 'logmar' nor 'stimSizeDeg' found in conditions file")

print(f"Size range: {min_size} to {max_size} degrees of visual angle")

# Sort by stimulus size (largest to smallest)
trial_conditions = sorted(trial_conditions, key=lambda x: x['stimSizeDeg'], reverse=True)

expanded_trial_list = []
for condition in trial_conditions:
    for _ in range(N_TRIALS_PER_SIZE):
        expanded_trial_list.append(condition.copy())

n_sizes = len(trial_conditions)
n_total_trials_per_block = n_sizes * N_TRIALS_PER_SIZE
print(f"Loaded {n_sizes} stimulus sizes from {CONDITIONS_FILE}.")
print(f"Total trials per main block part: {n_total_trials_per_block}")


# --- Setup Trial Handlers ---
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


# --- Helper Functions ---
def show_message(text_stim, wait_keys=['space', 'return', 'enter']):
    """Displays a TextStim and waits for a key press."""
    text_stim.draw()
    win.flip()
    event.waitKeys(keyList=wait_keys)
    win.flip()

def collect_yes_no_response(prompt_stim):
    """Collects a yes/no response and returns True for yes, False for no."""
    prompt_stim.draw()
    response_target_example.draw()
    win.flip()
    keys = event.waitKeys(keyList=['y', 'n', 'escape'])
    
    if 'escape' in keys:
        print("User aborted experiment.")
        core.quit()
    elif 'y' in keys:
        response = True
    else:  
        response = False

    win.flip() 
    return response


def run_rsvp_trial(win, stim_size_deg, item_duration_frames, require_response=True, end_fix_duration=FIXATION_POST_STREAM_RESPONSE_DUR):
    """Runs a single RSVP trial with Landolt C target and distractor images."""
    
    # Print size information for debugging
    print(f"Trial using stimulus size: {stim_size_deg} degrees")
    
    target_present = random.random() < (TARGET_PRESENT_PERCENT / 100.0)
    
    target_position = None
    if target_present:
        target_position = random.randint(TARGET_POS_MIN, TARGET_POS_MAX) 
    
    stream = []
    for i in range(N_STREAM_ITEMS):
        if target_present and i == target_position:
            stream.append("target") 
        else:
            distractor_idx = random.randint(0, len(distractor_images) - 1)
            while stream and stream[-1] == distractor_idx:
                distractor_idx = random.randint(0, len(distractor_images) - 1)
            stream.append(distractor_idx)
    
    fixation_cross.draw()
    win.flip()
    core.wait(FIXATION_PRE_STREAM_DUR)
    
    for i, item in enumerate(stream):
        if item == "target":
            rsvp_stim.image = target_image.image 
        else:
            rsvp_stim.image = distractor_images[item].image
        
        # Set stimulus size and print for debugging
        rsvp_stim.size = (stim_size_deg, stim_size_deg)
        
        for frame in range(item_duration_frames):
            if i == 0 and frame == 0:
                send_trigger(port, TRIGGER_STREAM_START)
                # Print the actual size that was set
                print(f"First frame actual size: {rsvp_stim.size}")
            
            if target_present and i == target_position and frame == 0:
                send_trigger(port, TRIGGER_TARGET_ONSET)
                # Print target size
                print(f"Target frame actual size: {rsvp_stim.size}")
            
            rsvp_stim.draw()
            win.flip()

    fixation_cross.draw()
    
    send_trigger(port, TRIGGER_STREAM_END)
    
    win.flip()
    core.wait(end_fix_duration)
    win.flip() 
    
    response = None
    accuracy = None
    if require_response:
        response = collect_yes_no_response(response_prompt_text)
        accuracy = 1 if response == target_present else 0
    else:
        response = 'N/A'
        accuracy = 'N/A'

    return target_present, target_position, response, accuracy

# --- Run Experiment ---

# Welcome Screen
show_message(welcome_text)

# Instruction Screen
instruction_text.draw()
win.flip()
event.waitKeys(keyList=['space', 'return', 'enter'])
win.flip() # Clear screen after key press

# Target Display Screen
target_display_text.draw()
instruction_target_example.draw()
win.flip()
event.waitKeys(keyList=['space', 'return', 'enter'])
win.flip()

#Practice Run
show_message(practice_instruction_text)
current_trial_global = 0 # Keep track of overall trial number
for trial_num_practice, practice_trial_data in enumerate(practice_handler):
    current_trial_global += 1
    stim_size = practice_trial_data['stimSizeDeg'] 
    
    target_present, target_pos, resp, acc = run_rsvp_trial(win,
                                             stim_size_deg=stim_size,
                                             item_duration_frames=PRACTICE_DURATION_FRAMES,
                                             require_response=True,
                                             end_fix_duration=FIXATION_POST_STREAM_RESPONSE_DUR)

    practice_handler.addData('block_type', 'practice')
    practice_handler.addData('trial_num_block', trial_num_practice + 1)
    practice_handler.addData('trial_num_global', current_trial_global)
    practice_handler.addData('target_present', target_present)
    practice_handler.addData('target_position', target_pos)
    practice_handler.addData('stim_size_deg', stim_size)
    practice_handler.addData('response', resp)
    practice_handler.addData('accuracy', acc)
    exp.nextEntry()

    if trial_num_practice < N_PRACTICE_TRIALS - 1:
        show_message(next_trial_text, wait_keys=['space'])


# --- Main Experiment Blocks ---

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

    exp.addLoop(trials_response) 
    for trial_num_block, trial_data in enumerate(trials_response):
        current_trial_global += 1
        stim_size = trial_data['stimSizeDeg']

        target_present, target_pos, resp, acc = run_rsvp_trial(
            win,
            stim_size_deg=stim_size,
            item_duration_frames=ITEM_DURATION_FRAMES,
            require_response=True,
            end_fix_duration=FIXATION_POST_STREAM_RESPONSE_DUR
        )

        trials_response.addData('block_type', f'{block_prefix}_response')
        trials_response.addData('trial_num_block', trial_num_block + 1)
        trials_response.addData('trial_num_global', current_trial_global)
        trials_response.addData('target_present', target_present)
        trials_response.addData('target_position', target_pos)
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

    exp.addLoop(trials_no_response)
    for trial_num_block, trial_data in enumerate(trials_no_response):
        current_trial_global += 1
        stim_size = trial_data['stimSizeDeg']

        target_present, target_pos, resp, acc = run_rsvp_trial(
            win,
            stim_size_deg=stim_size,
            item_duration_frames=ITEM_DURATION_FRAMES,
            require_response=False, # Key difference
            end_fix_duration=FIXATION_POST_STREAM_NO_RESPONSE_DUR # Key difference
        )

        trials_no_response.addData('block_type', f'{block_prefix}_no_response')
        trials_no_response.addData('trial_num_block', trial_num_block + 1)
        trials_no_response.addData('trial_num_global', current_trial_global)
        trials_no_response.addData('target_present', target_present)
        trials_no_response.addData('target_position', target_pos)
        trials_no_response.addData('response', resp) # Will be 'N/A'
        trials_no_response.addData('accuracy', acc) # Will be 'N/A'
        exp.nextEntry()

        is_last_overall_trial = (eye == 'right' and trial_num_block == n_total_trials_per_block - 1)
        if not is_last_overall_trial:
             show_message(next_trial_text, wait_keys=['space'])

    if eye == 'left':
        show_message(switch_to_right_eye_text)


# --- End of Experiment ---
goodbye_text.draw()
win.flip()
core.wait(3.0)


exp.saveAsWideText(filename + '.csv')
exp.saveAsPickle(filename + '.psydat')

# Reset parallel port at experiment end if it was initialized
if port is not None and PARALLEL_PORT_AVAILABLE:
    port.setData(0)

# --- Cleanup ---
win.close()
core.quit()
