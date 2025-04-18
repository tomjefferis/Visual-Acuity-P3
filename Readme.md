# Visual Acuity RSVP Experiment

The experiment (`rsvp_experiment_letters.py`) presents rapid streams of stimuli where participants need to identify target letters among number distractors. The experiment varies the size of the stimuli based on LogMAR values to determine visual acuity thresholds.

### Features

- **Eye-specific Testing**: Separate blocks for left and right eyes
- **Adaptive Sizing**: Presents stimuli at various sizes defined by LogMAR values
- **RSVP Paradigm**: Rapid serial presentation with one target letter per stream
- **Response Collection**: Records participant responses and accuracy
- **EEG Trigger Support**: Compatible with EEG/eye-tracking systems via serial port triggers

### Experimental Design

The experiment follows this structure:
1. Practice trials (easier, slightly slower presentation)
2. Left eye testing (with response)
3. Left eye testing (passive viewing)
4. Right eye testing (with response)
5. Right eye testing (passive viewing)

## Installation

### Requirements
- Python 3.10 <- Newer python versions are reported to have compatibility issues
- PsychoPy 2025.1.0

### Quick Setup (using Conda)

1. Clone this repository to your local machine:
   ```
   git clone https://github.com/yourusername/Visual-Acuity.git
   cd Visual-Acuity
   ```

2. Run the setup script to create a Conda environment and install dependencies:
   ```
   ./exp_setup.sh
   ```

3. Activate the environment:
   ```
   source activate .conda
   ```

### Manual Setup

If you prefer to set up manually:

1. Create a new Conda environment:
   ```
   conda create --name visualacuity python=3.10
   conda activate visualacuity
   ```

2. Install required packages:
   ```
   pip install -r requirements.txt
   ```

## Running the Experiment

To run the main RSVP letters experiment:

```
python rsvp_experiment_letters.py
```

The script will prompt you to enter participant information and then guide you through the experimental procedure.
