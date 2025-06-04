"""
PsychoPy script for an RSVP (Rapid Serial Visual Presentation) experiment.
Presents streams of letters (target) and numbers (distractors) at varying sizes.
Collects target identification responses for some blocks.
Runs separate blocks for left and right eyes.
Includes a photodiode patch for precise timing measurement.
"""

from psychopy import core, visual, gui, data, event, logging, monitors
import labjackU3
import random
import numpy as np  # Adding numpy for better random number generation
import os
import csv
from datetime import datetime

# --- Constants ---
TARGET_LETTERS = ['C', 'D', 'H', 'K', 'N', 'F', 'R', 'S', 'V', 'Z']
DISTRACTORS = [str(i) for i in range(1, 10)]
N_STREAM_ITEMS = 16
TARGET_POS_MIN = 5 
TARGET_POS_MAX = 8 
FIXATION_PRE_STREAM_DUR = 0.700 
FIXATION_POST_STREAM_RESPONSE_DUR = 0.5 
FIXATION_POST_STREAM_NO_RESPONSE_DUR = 1.000 
FIXATION_SYMBOLS = ['-', '=']  # Symbols used for the end of stream - changed from + to -

# --- Pseudorandom sequence generation ---
# Use a fixed seed for reproducibility
RANDOM_SEED = 42

# --- Photodiode constants ---
PHOTODIODE_SIZE = 0.8  # Size in degrees of visual angle
PHOTODIODE_POSITION = (4, -2)  # Position at bottom right (adjust based on your screen)

# --- Item Duration ---
ITEM_DURATION_MS = 120  # Target duration in milliseconds
PRACTICE_SPEED_FACTOR = 0.75  # Practice speed 0-1

N_TRIALS_PER_SIZE = 16
N_PRACTICE_TRIALS = 2 
CONDITIONS_FILE = 'conditions.csv'
DATA_FOLDER = 'data' # Folder to save data files

# --- Trigger Values ---
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

def initialize_labjack():
    """Initialize the LabJack U3 for sending triggers."""
    try:
        # Configure the LabJack using our custom implementation
        labjackU3.configure()
        print("LabJack U3 initialized successfully")
        return True  # Return True to indicate success instead of the device object
    except Exception as e:
        print(f"ERROR: Failed to initialize LabJack U3: {e}")
        return None


def send_trigger(ljack, trigger_value):
    """Send a trigger value to the LabJack U3."""
    if ljack is not None:
        # Use our custom labjackU3 module to send the trigger
        labjackU3.trigger(trigger_value)
        logging.exp(f"TRIGGER: Sent value {trigger_value} to LabJack U3")
    else:
        logging.exp(f"TRIGGER: LabJack not available, cannot send value {trigger_value}")


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
    size_degrees = size_arcmin / 30.0 # not sure why, but the font used is 30 arcmin
    
    return size_degrees

# --- Experiment Setup ---
exp_info = {
    'Participant ID': '',
    'Age': '',
    'Gender': ('Male', 'Female', 'Other', 'Prefer not to say'),
    'Ethnicity': '',
    'Handedness': ('Left', 'Right', 'Ambidextrous'),
    'Vision': ('Normal', 'Corrected', 'Impaired'),
    'Glasses/Contacts': ('Yes', 'No'),
    'Eye Dominance': ('Left', 'Right', 'No preference', 'Not sure'),
    'Hours of Sleep last night': '',
    'Hours of computer use today': '',
    'Hours of computer games this week': '',
    'Viewing Distance (cm)': 300,
    'Test Mode': ('No', 'Yes'),  # Added test mode option
}

dlg = gui.DlgFromDict(dictionary=exp_info, title='Experiment Setup', order=['Participant ID', 'Age','Gender', 'Ethnicity', 'Handedness', 'Vision', 'Glasses/Contacts', 'Eye Dominance', 'Hours of Sleep last night', 'Hours of computer use today', 'Hours of computer games this week', 'Viewing Distance (cm)', 'Test Mode'])
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
mon.setWidth(47.8)
mon.setSizePix((1920,1080))  # Set to your screen resolution
print(f"Monitor res: {mon.getSizePix()} px")
mon.save()

win = visual.Window(
    size=mon.getSizePix(),
    fullscr=True,
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

actual_frame_rate = win.getActualFrameRate(nIdentical=10, nMaxFrames=200, nWarmUpFrames=10, threshold=1)
if actual_frame_rate is not None:
    exp_info['frameRate'] = actual_frame_rate
    frameDur = 1.0 / round(actual_frame_rate)
    print(f"Measured refresh rate: {actual_frame_rate:.2f} Hz (frame duration: {frameDur*1000:.2f} ms)")
else:
    exp_info['frameRate'] = 60.0
    frameDur = 1.0 / 60.0
    logging.warning("Could not measure frame rate, assuming 60Hz.")
    print("WARNING: Could not measure frame rate, assuming 60Hz.")

ITEM_DURATION_FRAMES = max(1, round(ITEM_DURATION_MS / (frameDur * 1000)))
PRACTICE_DURATION_FRAMES = max(1, round((ITEM_DURATION_MS / PRACTICE_SPEED_FACTOR) / (frameDur * 1000)))
print(f"Item duration: {ITEM_DURATION_FRAMES} frames ({ITEM_DURATION_FRAMES * frameDur * 1000:.2f} ms)")
print(f"Practice duration: {PRACTICE_DURATION_FRAMES} frames ({PRACTICE_DURATION_FRAMES * frameDur * 1000:.2f} ms)")

ljack = initialize_labjack()


snellen_font = 'Optician Sans'  # Font for stimuli


welcome_text = visual.TextStim(win=win, text="Welcome to the experiment!\nPress SPACE or ENTER to continue.", height=0.5, wrapWidth=25)
instruction_text = visual.TextStim(win=win, text=(
    "Instructions:\n"
    "You will see a rapid stream of items in the center of the screen.\n"
    "Each stream contains numbers and ONE letter.\n"
    "Your tasks are to:\n"
    "1) Identify the LETTER in the stream.\n"
    "2) Identify the symbol at the end of the stream (- or =).\n"
    "First, there will be a short practice.\n"
    "Press SPACE or ENTER to start the practice."), height=0.3, wrapWidth=20)
practice_instruction_text = visual.TextStim(win=win, text="Practice Run\nPress SPACE or ENTER to begin.", height=0.3, wrapWidth=25)
left_eye_instruction_text = visual.TextStim(win=win, text="Left Eye Block - Part 1\nPlease cover your RIGHT eye now.\nYou will need to identify: \n1) the letter in each trial and \n2) the end symbol (- or =).\nPress SPACE or ENTER to begin.", height=0.3, wrapWidth=20)
right_eye_instruction_text = visual.TextStim(win=win, text="Right Eye Block - Part 1\nPlease cover your LEFT eye now.\nYou will need to identify: \n1) the letter in each trial and \n2) the end symbol (- or =).\nPress SPACE or ENTER to begin.", height=0.3, wrapWidth=20)
left_eye_no_response_text = visual.TextStim(win=win, text="Left Eye Block - Part 2\nKeep your RIGHT eye covered.\nIn this part, you do NOT need to identify the letter, \nbut you still need to identify the end symbol (- or =).\nPress SPACE or ENTER to begin.", height=0.3, wrapWidth=20)
right_eye_no_response_text = visual.TextStim(win=win, text="Right Eye Block - Part 2\nKeep your LEFT eye covered.\nIn this part, you do NOT need to identify the letter, \nbut you still need to identify the end symbol (- or =).\nPress SPACE or ENTER to begin.", height=0.3, wrapWidth=20)
switch_to_right_eye_text = visual.TextStim(win=win, text="Left Eye Block Complete\nNow we\\'ll switch to your RIGHT eye.\nPlease take a short break if needed.\nPress SPACE or ENTER when you\\'re ready to continue.", height=0.3, wrapWidth=20)
fixation_cross = visual.TextStim(win=win, text='+', height=1, font=snellen_font)
minus_sign = visual.TextStim(win=win, text='-', height=1, font=snellen_font)  # New stimulus for minus sign
equal_sign = visual.TextStim(win=win, text='=', height=1, font=snellen_font) # New stimulus for equals sign
response_prompt_text = visual.TextStim(win=win, text="Which letter did you see?\n(Type the letter and press ENTER)", height=0.5, wrapWidth=20)
typed_response_text = visual.TextStim(win=win, text="", height=1, pos=(0, -2))
symbol_prompt_text = visual.TextStim(win=win, text="What symbol was shown at the end?\n(- or =)\n(Type - or = and press ENTER)", height=0.5, wrapWidth=20) # Updated prompt for symbol
typed_symbol_text = visual.TextStim(win=win, text="", height=1.5, pos=(0, -2)) # New text for typed symbol
next_trial_text = visual.TextStim(win=win, text="Press SPACE to start the next trial.", height=0.5, wrapWidth=20)
goodbye_text = visual.TextStim(win=win, text="Thank you for participating!\nThe experiment is now complete.", height=0.5, wrapWidth=25)


rsvp_stim = visual.TextStim(win=win, text='', height=1.0, font=snellen_font) 

# Create photodiode patch stimulus (circular)
photodiode_patch = visual.Circle(win=win,
                             radius=PHOTODIODE_SIZE/2,  # Radius is half the size
                             pos=PHOTODIODE_POSITION,
                             fillColor='black',
                             lineColor=None)

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

def collect_response(prompt_stim, typed_stim, expected_chars_list=None):
    """Collects a typed response until Enter is pressed.
    Handles mapping of PsychoPy key names to characters for letters, '+', '-', and '='.
    Correctly interprets Shift + '=' as '+'.
    """
    response_str = ""
    typed_stim.text = ""
    # Initial prompt display is now done after setting up listeners

    # PsychoPy key names and their corresponding characters (for direct mapping)
    # The 'equal' key is handled specially below to check for the Shift modifier.
    key_name_to_char_map = {
        'a': 'A', 'b': 'B', 'c': 'C', 'd': 'D', 'e': 'E', 'f': 'F', 'g': 'G',
        'h': 'H', 'i': 'I', 'j': 'J', 'k': 'K', 'l': 'L', 'm': 'M', 'n': 'N',
        'o': 'O', 'p': 'P', 'q': 'Q', 'r': 'R', 's': 'S', 't': 'T', 'u': 'U',
        'v': 'V', 'w': 'W', 'x': 'X', 'y': 'Y', 'z': 'Z',
        'plus': '+',        # For a dedicated '+' key (e.g., on numpad or some keyboards)
        'minus': '-',       # For a dedicated '-' key
        'kp_add': '+',      # Numpad '+'
        'kp_subtract': '-', # Numpad '-'
        'kp_equal': '=',    # Numpad '=' (if it exists and is used)
    }

    active_allowed_chars = []
    # Determine active_allowed_chars based on the prompt type
    if prompt_stim == symbol_prompt_text: # Symbol prompt
        # expected_chars_list is ['-', '='] when called for symbol prompt
        active_allowed_chars = [char.upper() for char in expected_chars_list if char in ['+', '-', '=']] if expected_chars_list else ['-', '=']
    elif prompt_stim == response_prompt_text: # Letter prompt
        # expected_chars_list is None when called for letter prompt
        active_allowed_chars = [chr(ord('A') + i) for i in range(26)] # Default to all uppercase letters
        if expected_chars_list: # This part is not currently used but allows for future restriction
            # active_allowed_chars = [char.upper() for char in expected_chars_list if char.isalpha()]
            pass


    # Determine which base key names to listen for
    base_listen_keys = ['backspace', 'return', 'enter', 'escape']
    # Check if any uppercase letter A-Z is in active_allowed_chars
    if any(chr(ord('A') + i) in active_allowed_chars for i in range(26)):
        for i in range(26):
            base_listen_keys.append(chr(ord('a') + i)) # Listen for 'a', 'b', ...

    if '+' in active_allowed_chars or '-' in active_allowed_chars or '=' in active_allowed_chars:
        base_listen_keys.extend(['equal', 'plus', 'minus', 'kp_add', 'kp_subtract', 'kp_equal'])

    listen_for_key_names = list(set(base_listen_keys)) # Ensure unique key names

    # Initial display of prompt
    prompt_stim.draw()
    typed_stim.draw() # Initially empty
    win.flip()

    break_loop = False
    while not break_loop:
        # Get all key events in this frame, with modifiers
        keys_with_mods = event.getKeys(keyList=listen_for_key_names, modifiers=True)

        if not keys_with_mods: 
            prompt_stim.draw()
            typed_stim.draw()
            win.flip()
            core.wait(0.001) 
            continue 

        # Process each key event from this frame
        for key_name_pressed, mods in keys_with_mods:
            if key_name_pressed in ['escape']:
                print("User aborted experiment.")
                core.quit() 
                return ""  # Should not be reached if core.quit() works
            
            elif key_name_pressed in ['return', 'enter']:
                if response_str: # Only accept if there's a response
                    break_loop = True # Signal to break outer while-loop
                    break # Exit this inner for-loop (over keys_with_mods)
                else:
                    # No response yet, ignore enter, continue processing other keys in this frame if any
                    continue 
            
            elif key_name_pressed == 'backspace':
                response_str = response_str[:-1]
                # typed_stim.text will be updated before the flip
            
            else: # Character input keys
                char_to_add = None
                is_shift_pressed = mods.get('shift', False)

                if key_name_pressed == 'equal': # Handle '=' and Shift+'=' -> '+'
                    char_to_add = '+' if is_shift_pressed else '='
                elif key_name_pressed == 'minus': # Handle '-' key
                    char_to_add = '-'
                elif key_name_pressed in key_name_to_char_map: # For letters and other mapped keys
                    char_to_add = key_name_to_char_map[key_name_pressed]
                
                if char_to_add and char_to_add in active_allowed_chars:
                    if prompt_stim == symbol_prompt_text:
                        # For symbol prompt, overwrite to ensure only one symbol
                        response_str = char_to_add
                    elif prompt_stim == response_prompt_text: # For letter prompt, append
                        response_str += char_to_add
        
        # After processing all keys for this frame, update display
        typed_stim.text = response_str
        prompt_stim.draw()
        typed_stim.draw()
        win.flip()

    # break_loop is true, meaning 'return'/'enter' was pressed with a valid response
    win.flip() # Clear the prompt/response from screen
    return response_str

def run_rsvp_trial(win, stim_size_deg, item_duration_frames, require_response=True, end_fix_duration=FIXATION_POST_STREAM_RESPONSE_DUR):
    # Create a seeded random number generator for this trial
    # We use the participant ID and trial parameters to create a unique but reproducible seed
    seed_value = int(hash(str(exp_info['Participant ID']) + str(stim_size_deg) + str(require_response)) % 2**32)
    rng = np.random.RandomState(seed_value)
    
    # Use the seeded RNG for all "random" choices
    target_letter = TARGET_LETTERS[rng.randint(0, len(TARGET_LETTERS))]
    target_position = rng.randint(TARGET_POS_MIN, TARGET_POS_MAX + 1)  # +1 because randint upper bound is exclusive
    end_symbol = FIXATION_SYMBOLS[rng.randint(0, len(FIXATION_SYMBOLS))]  # Random + or =

    stream = []
    for i in range(N_STREAM_ITEMS):
        if i == target_position:
            stream.append(target_letter)
        else:
            # Choose a distractor that's different from the last item in the stream
            while True:
                distractor_idx = rng.randint(0, len(DISTRACTORS))
                distractor = DISTRACTORS[distractor_idx]
                if not stream or distractor != stream[-1]:
                    break
            stream.append(distractor)

    # Display fixation cross before the stream
    fixation_cross.draw()
    # Set photodiode patch to black for the fixation period
    photodiode_patch.fillColor = 'black'
    photodiode_patch.draw()
    win.flip()
    core.wait(FIXATION_PRE_STREAM_DUR)

    # RSVP stream presentation
    for i, item in enumerate(stream):
        rsvp_stim.setText(item)
        rsvp_stim.height = stim_size_deg
        
        for frame in range(item_duration_frames):
            if i == 0 and frame == 0:
                send_trigger(ljack, TRIGGER_STREAM_START)
                logging.exp(f"RSVP Stream Start - Item: {item}")
            
            if i == target_position and frame == 0:
                send_trigger(ljack, TRIGGER_TARGET_ONSET)
                logging.exp(f"Target Letter Onset - Letter: {item}")
            
            if frame == 0:
                # Send item-specific trigger for each stimulus
                send_trigger(ljack, TRIGGER_MAP[item])
                logging.exp(f"Stimulus Onset - Item: {item}, Trigger: {TRIGGER_MAP[item]}")
                
                # Set photodiode patch to white at the onset of each stimulus
                photodiode_patch.fillColor = 'white'
            
            # Draw stimulus and photodiode patch
            rsvp_stim.draw()
            photodiode_patch.draw()
            win.flip()
            
            # Set photodiode patch back to black after the first frame
            if frame == 0:
                photodiode_patch.fillColor = 'black'

    # Display the end symbol (- or =)
    if end_symbol == '-':
        minus_sign.draw()
    else:
        equal_sign.draw()
    
    # Set photodiode patch to black for the end symbol period
    photodiode_patch.fillColor = 'black'
    photodiode_patch.draw()
    
    send_trigger(ljack, TRIGGER_STREAM_END)
    logging.exp(f"RSVP Stream End - End symbol: {end_symbol}") # Log the chosen end symbol
    
    win.flip()
    core.wait(end_fix_duration) # Display the end symbol for the specified duration
    win.flip() # Clear the screen

    letter_response = None
    letter_accuracy = None
    symbol_response = None
    symbol_accuracy = None

    if require_response:
        letter_response = collect_response(response_prompt_text, typed_response_text, expected_chars_list=None) # Defaults to A-Z
        letter_accuracy = 1 if letter_response == target_letter else 0
    else:
        letter_response = 'N/A'
        letter_accuracy = 'N/A'
    
    # Always collect symbol response
    symbol_response = collect_response(symbol_prompt_text, typed_symbol_text, expected_chars_list=['+', '='])
    symbol_accuracy = 1 if symbol_response == end_symbol else 0

    return target_letter, target_position, stream, letter_response, letter_accuracy, end_symbol, symbol_response, symbol_accuracy

def run_font_size_test_mode(win):
    """
    Test mode to display a sample letter at each font size.
    User presses space to advance through sizes, from largest to smallest.
    No data is saved in this mode.
    """
    test_instruction_text = visual.TextStim(win=win, text="Font Size Test Mode\nA sample letter will be shown at each size.\nPress SPACE to advance to the next size.\nPress SPACE to begin.", height=0.5, wrapWidth=25)
    show_message(test_instruction_text)
    
    test_stim = visual.TextStim(win=win, text='R', height=1.0, font=snellen_font)  # Using 'A' as a standard test letter
    size_info_text = visual.TextStim(win=win, text='', pos=(0, -3), height=0.5, wrapWidth=20.5)
    
    # Sort conditions from largest to smallest size
    sorted_conditions = sorted(trial_conditions, key=lambda x: x['stimSizeDeg'], reverse=True)
    
    for condition in sorted_conditions:
        stim_size = condition['stimSizeDeg']
        logmar = condition.get('logmar', 'N/A')
        
        # Display the letter at this size
        test_stim.height = stim_size
        size_info_text.text = f"Size: {stim_size:.4f} degrees (LogMAR: {logmar})"
        
        test_stim.draw()
        size_info_text.draw()
        win.flip()
        
        # Wait for space bar press to continue to next size
        event.waitKeys(keyList=['space', 'escape'])
        
        # Check if escape was pressed to exit
        if 'escape' in event.getKeys():
            break
    
    # Test complete message
    test_complete_text = visual.TextStim(win=win, text="Font size test complete.\nPress SPACE to exit.")
    test_complete_text.draw()
    win.flip()
    event.waitKeys(keyList=['space', 'escape'])

show_message(welcome_text)

# Check if test mode is enabled
if exp_info['Test Mode'] == 'Yes':
    # Run test mode
    run_font_size_test_mode(win)
    
    # Exit after test mode is complete
    goodbye_text = visual.TextStim(win=win, text="Font size test complete.\nThank you!", height=1.0)
    goodbye_text.draw()
    win.flip()
    core.wait(2.0)
      # Clean up and exit
    if ljack is not None:
        labjackU3.trigger(0)  # Reset the trigger to 0
        logging.exp("LabJack reset at experiment end")
    
    win.close()
    core.quit()
else:
    # Continue with normal experiment flow
    show_message(instruction_text)
    
    show_message(practice_instruction_text)
    current_trial_global = 0
    for trial_num_practice, practice_trial_data in enumerate(practice_handler):
        current_trial_global += 1
        stim_size = practice_trial_data['stimSizeDeg']
        
        target, pos, stream_items, l_resp, l_acc, e_sym, s_resp, s_acc = run_rsvp_trial(win,
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
        practice_handler.addData('letter_response', l_resp)
        practice_handler.addData('letter_accuracy', l_acc)
        practice_handler.addData('end_symbol', e_sym)
        practice_handler.addData('symbol_response', s_resp)
        practice_handler.addData('symbol_accuracy', s_acc)
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

            target, pos, stream_items, l_resp, l_acc, e_sym, s_resp, s_acc = run_rsvp_trial(
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
            trials_response.addData('stim_size_deg', stim_size) # Added missing stim_size_deg
            trials_response.addData('letter_response', l_resp)
            trials_response.addData('letter_accuracy', l_acc)
            trials_response.addData('end_symbol', e_sym)
            trials_response.addData('symbol_response', s_resp)
            trials_response.addData('symbol_accuracy', s_acc)
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

            target, pos, stream_items, l_resp, l_acc, e_sym, s_resp, s_acc = run_rsvp_trial(
                win,
                stim_size_deg=stim_size,
                item_duration_frames=ITEM_DURATION_FRAMES,
                require_response=False, # Letter response not required
                end_fix_duration=FIXATION_POST_STREAM_NO_RESPONSE_DUR
            )

            trials_no_response.addData('block_type', f'{block_prefix}_no_response')
            trials_no_response.addData('trial_num_block', trial_num_block + 1)
            trials_no_response.addData('trial_num_global', current_trial_global)
            trials_no_response.addData('target_letter', target)
            trials_no_response.addData('target_position', pos)
            trials_no_response.addData('stim_size_deg', stim_size) # Added missing stim_size_deg
            trials_no_response.addData('letter_response', l_resp) # Will be 'N/A'
            trials_no_response.addData('letter_accuracy', l_acc) # Will be 'N/A'
            trials_no_response.addData('end_symbol', e_sym)
            trials_no_response.addData('symbol_response', s_resp)
            trials_no_response.addData('symbol_accuracy', s_acc)
            exp.nextEntry()

            if trial_num_block < n_total_trials_per_block - 1:
                show_message(next_trial_text, wait_keys=['space'])
            else:
                core.wait(1.0) # Wait a bit after the last trial of the no-response block

        if eye == 'left':
            show_message(switch_to_right_eye_text)

# --- End of Experiment ---
goodbye_text.draw()
win.flip()
core.wait(3.0)

exp.saveAsWideText(filename + '.csv')
exp.saveAsPickle(filename + '.psydat')
logging.flush()

if ljack is not None:
    labjackU3.trigger(0)  # Reset the trigger to 0
    logging.exp("LabJack reset at experiment end")

win.close()
core.quit()