"""
PsychoPy script for an RSVP (Rapid Serial Visual Presentation) experiment.
Presents streams of letters (target) and numbers (distractors) at varying contrast levels.
Collects target identification responses for some blocks.
Runs separate blocks for left and right eyes.
"""

from psychopy import core, visual, gui, data, event, logging, monitors
import random
import os
import csv
from datetime import datetime

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
TRIGGER_STREAM_START = 1    # First item onset
TRIGGER_TARGET_ONSET = 2    # Target presentation 
TRIGGER_STREAM_END = 3      # End of stream (post-stream fixation onset)
TRIGGER_DURATION_MS = 10    # Duration to keep trigger on (in ms)

# Default port address for parallel port
PARALLEL_PORT_ADDRESS = 0x378  # Standard address, may need adjustment for the system

# --- Item Duration ---
# Will determine item duration in frames based on measured refresh rate
ITEM_DURATION_MS = 100  # Target duration in milliseconds
PRACTICE_SPEED_FACTOR = 1  # Practice speed

N_TRIALS_PER_CONTRAST = 1
N_PRACTICE_TRIALS = 2 
CONDITIONS_FILE = 'contrast_conditions.csv'
DATA_FOLDER = 'data' # Folder to save data files
STIM_SIZE_DEG = 1.0  # Fixed stimulus size in degrees of visual angle

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
        logging.exp(f"TRIGGER: Sent value {trigger_value} to parallel port")
        core.wait(TRIGGER_DURATION_MS/1000.0)
        port.setData(0)
    else:
        logging.exp(f"TRIGGER: Simulated sending value {trigger_value} to parallel port")

# --- Michelson Contrast Conversion ---
def contrast_pct_to_color_value(contrast_pct, background_color=0):
    """
    Convert contrast percentage to PsychoPy color value.
    
    Michelson contrast = (Lmax - Lmin) / (Lmax + Lmin)
    Where Lmax is stimulus luminance and Lmin is background luminance
    
    Args:
        contrast_pct (float): Contrast percentage (0-100)
        background_color (float): Background color value (-1 to 1 in PsychoPy)
        
    Returns:
        float: Color value for stimulus (-1 to 1 in PsychoPy)
    """
    # Convert percentage to proportion (0-1)
    contrast = contrast_pct / 100.0
    
    # In PsychoPy's -1 to 1 scale, where 0 is mid-gray
    # For a gray background (0), with contrast c, the formula simplifies
    bg = background_color
    
    # For dark stimuli on light background
    stim_color = bg - contrast * (1 - bg)
    
    return stim_color

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

exp = data.ExperimentHandler(name='RSVP_Contrast', version='1.0',
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

port = initialize_parallel_port()

welcome_text = visual.TextStim(win=win, text="Welcome to the experiment!\n\nPress SPACE or ENTER to continue.", height=1.0, wrapWidth=30, color=-1)
instruction_text = visual.TextStim(win=win, text=(
    "Instructions:\n\n"
    "You will see a rapid stream of items in the center of the screen.\n"
    "Each stream contains numbers and ONE letter.\n"
    "Your task is to identify the LETTER.\n\n"
    "First, there will be a short practice.\n\n"
    "Press SPACE or ENTER to start the practice."), height=0.8, wrapWidth=30, color=-1)
practice_instruction_text = visual.TextStim(win=win, text="Practice Run (Slightly Slower)\n\nPress SPACE or ENTER to begin.", height=1.0, wrapWidth=30, color=-1)
left_eye_instruction_text = visual.TextStim(win=win, text="Left Eye Block - Part 1 (With Response)\n\nPlease cover your RIGHT eye now.\n\nYou will need to identify the letter in each trial.\n\nPress SPACE or ENTER to begin.", height=1.0, wrapWidth=30, color=-1)
right_eye_instruction_text = visual.TextStim(win=win, text="Right Eye Block - Part 1 (With Response)\n\nPlease cover your LEFT eye now.\n\nYou will need to identify the letter in each trial.\n\nPress SPACE or ENTER to begin.", height=1.0, wrapWidth=30, color=-1)
left_eye_no_response_text = visual.TextStim(win=win, text="Left Eye Block - Part 2 (No Response)\n\nKeep your RIGHT eye covered.\n\nIn this part, you do NOT need to respond.\nSimply watch the streams carefully.\n\nPress SPACE or ENTER to begin.", height=1.0, wrapWidth=30, color=-1)
right_eye_no_response_text = visual.TextStim(win=win, text="Right Eye Block - Part 2 (No Response)\n\nKeep your LEFT eye covered.\n\nIn this part, you do NOT need to respond.\nSimply watch the streams carefully.\n\nPress SPACE or ENTER to begin.", height=1.0, wrapWidth=30, color=-1)
switch_to_right_eye_text = visual.TextStim(win=win, text="Left Eye Block Complete\n\nNow we'll switch to your RIGHT eye.\n\nPlease take a short break if needed.\n\nPress SPACE or ENTER when you're ready to continue.", height=1.0, wrapWidth=30, color=-1)
fixation_cross = visual.TextStim(win=win, text='+', height=2, color=-1)
rsvp_stim = visual.TextStim(win=win, text='', height=STIM_SIZE_DEG, color=-1)
response_prompt_text = visual.TextStim(win=win, text="Which letter did you see?\n(Type the letter and press ENTER)", height=1.0, wrapWidth=30, color=-1)
typed_response_text = visual.TextStim(win=win, text="", height=1.5, pos=(0, -3), color=-1)
next_trial_text = visual.TextStim(win=win, text="Press SPACE to start the next trial.", height=1.0, wrapWidth=30, color=-1)
goodbye_text = visual.TextStim(win=win, text="Thank you for participating!\n\nThe experiment is now complete.", height=1.0, wrapWidth=30, color=-1)

kb = event.BuilderKeyResponse()

try:
    trial_conditions = data.importConditions(CONDITIONS_FILE)
    
    min_contrast = float('inf')
    max_contrast = float('-inf')
    
    for condition in trial_conditions:
        if 'contrastPct' in condition:
            contrast_pct = float(condition['contrastPct'])
            condition['stimColor'] = contrast_pct_to_color_value(contrast_pct, background_color)
            
            min_contrast = min(min_contrast, contrast_pct)
            max_contrast = max(max_contrast, contrast_pct)
            
            print(f"Converting contrast {contrast_pct}% to color value {condition['stimColor']}")
        elif 'stimColor' not in condition:
            raise ValueError("Neither 'contrastPct' nor 'stimColor' found in conditions file")
    
    print(f"Contrast range: {min_contrast}% to {max_contrast}%")
    
    # Sort from highest to lowest contrast for ease of testing
    trial_conditions = sorted(trial_conditions, key=lambda x: float(x['contrastPct']) if 'contrastPct' in x else -1, reverse=True)
    
    expanded_trial_list = []
    for condition in trial_conditions:
        for _ in range(N_TRIALS_PER_CONTRAST):
            expanded_trial_list.append(condition.copy())
    
    n_contrasts = len(trial_conditions)
    n_total_trials_per_block = n_contrasts * N_TRIALS_PER_CONTRAST
    print(f"Loaded {n_contrasts} contrast levels from {CONDITIONS_FILE}.")
    print(f"Total trials per main block part: {n_total_trials_per_block}")
except Exception as e:
    print(f"ERROR: Could not load conditions file '{CONDITIONS_FILE}'!")
    print(e)
    if not os.path.exists(CONDITIONS_FILE):
        print(f"Creating a default '{CONDITIONS_FILE}' with example contrast values.")
        default_contrasts = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 5, 2.5, 1.25]
        try:
            with open(CONDITIONS_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['contrastPct'])
                for contrast in default_contrasts:
                    writer.writerow([contrast])
            
            trial_conditions = data.importConditions(CONDITIONS_FILE)
            
            for condition in trial_conditions:
                contrast_pct = float(condition['contrastPct'])
                condition['stimColor'] = contrast_pct_to_color_value(contrast_pct, background_color)
                print(f"Converting contrast {contrast_pct}% to color value {condition['stimColor']}")
            
            trial_conditions = sorted(trial_conditions, key=lambda x: float(x['contrastPct']), reverse=True)
            
            expanded_trial_list = []
            for condition in trial_conditions:
                for _ in range(N_TRIALS_PER_CONTRAST):
                    expanded_trial_list.append(condition.copy())
                    
            n_contrasts = len(trial_conditions)
            n_total_trials_per_block = n_contrasts * N_TRIALS_PER_CONTRAST
            print(f"Loaded {n_contrasts} contrast levels from newly created {CONDITIONS_FILE}.")
            print(f"Total trials per main block part: {n_total_trials_per_block}")
        except Exception as e2:
            print(f"ERROR: Failed to create or load default conditions file.")
            print(e2)
            core.quit()
    else:
        core.quit()

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

def run_rsvp_trial(win, stim_color, item_duration_frames, require_response=True, end_fix_duration=FIXATION_POST_STREAM_RESPONSE_DUR):
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
        rsvp_stim.setColor(stim_color)
        
        for frame in range(item_duration_frames):
            if i == 0 and frame == 0:
                send_trigger(port, TRIGGER_STREAM_START)
                logging.exp(f"RSVP Stream Start - Item: {item}")
            
            if i == target_position and frame == 0:
                send_trigger(port, TRIGGER_TARGET_ONSET)
                logging.exp(f"Target Letter Onset - Letter: {item}")
            
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
    stim_color = practice_trial_data['stimColor']
    contrast_pct = practice_trial_data['contrastPct']
    
    target, pos, stream_items, resp, acc = run_rsvp_trial(win,
                                             stim_color=stim_color,
                                             item_duration_frames=PRACTICE_DURATION_FRAMES,
                                             require_response=True,
                                             end_fix_duration=FIXATION_POST_STREAM_RESPONSE_DUR)

    practice_handler.addData('block_type', 'practice')
    practice_handler.addData('trial_num_block', trial_num_practice + 1)
    practice_handler.addData('trial_num_global', current_trial_global)
    practice_handler.addData('target_letter', target)
    practice_handler.addData('target_position', pos)
    practice_handler.addData('contrast_pct', contrast_pct)
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
        stim_color = trial_data['stimColor']
        contrast_pct = trial_data['contrastPct']

        target, pos, stream_items, resp, acc = run_rsvp_trial(
            win,
            stim_color=stim_color,
            item_duration_frames=ITEM_DURATION_FRAMES,
            require_response=True,
            end_fix_duration=FIXATION_POST_STREAM_RESPONSE_DUR
        )

        trials_response.addData('block_type', f'{block_prefix}_response')
        trials_response.addData('trial_num_block', trial_num_block + 1)
        trials_response.addData('trial_num_global', current_trial_global)
        trials_response.addData('target_letter', target)
        trials_response.addData('target_position', pos)
        trials_response.addData('contrast_pct', contrast_pct)
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
        stim_color = trial_data['stimColor']
        contrast_pct = trial_data['contrastPct']

        target, pos, stream_items, resp, acc = run_rsvp_trial(
            win,
            stim_color=stim_color,
            item_duration_frames=ITEM_DURATION_FRAMES,
            require_response=False,
            end_fix_duration=FIXATION_POST_STREAM_NO_RESPONSE_DUR
        )

        trials_no_response.addData('block_type', f'{block_prefix}_no_response')
        trials_no_response.addData('trial_num_block', trial_num_block + 1)
        trials_no_response.addData('trial_num_global', current_trial_global)
        trials_no_response.addData('target_letter', target)
        trials_no_response.addData('target_position', pos)
        trials_no_response.addData('contrast_pct', contrast_pct)
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

if port is not None and PARALLEL_PORT_AVAILABLE:
    port.setData(0)
    logging.exp("Parallel port reset at experiment end")

win.close()
core.quit()