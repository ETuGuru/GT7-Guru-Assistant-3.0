# Python Virtual Environment

This directory contains the Python virtual environment for the project.

## Setup
1. Create virtual environment:
   ```
   python -m venv venv
   ```
2. Activate virtual environment:
   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`
3. Install dependencies:
   ```
   pip install -r ../requirements.txt
   ```

Note: The virtual environment directory is ignored by Git.

# Python Virtual Environment

This directory contains the Python virtual environment for the project.

## Setting up the Virtual Environment

1. Create a new virtual environment:
   `ash
   python -m venv venv
   `

2. Activate the virtual environment:
   - Windows:
     `ash
     .\venv\Scripts\activate
     `
   - Unix/MacOS:
     `ash
     source venv/bin/activate
     `

3. Install required packages:
   `ash
   pip install -r requirements.txt
   `

## Maintenance

- Keep requirements.txt updated with project dependencies
- Regularly update packages to maintain security
- Clean and rebuild the environment if issues arise

Note: The virtual environment directory is not tracked in git.
