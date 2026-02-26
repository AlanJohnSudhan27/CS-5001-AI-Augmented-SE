# Code Translation: In Class Exercise with Prompting

## prompts
Contains 2 files: `system-prompt.txt` and `user-prompt.txt`. 

## cpp_programs
Contains 18 CPP programs

## output_code_translation
Inclues two folders:
### Solution: Saves your output in this folder. Please do not change this folder name as Tests depends on the exact name.
### Test: The test files for the python codes.

## code_translation.py
Run this python file to generate the code translation.

# How to Run Translation:
```
python code_translation.py --user-prompt-file prompts/user-prompt.txt --system-prompt-file prompts/system-prompt.txt
```

# How to Run Test:
Go to `output_code_translation` folder. Then run:
```
python -m unittest discover -s test -v
```

# Instructions
- Go the the test output errors and understand what are the common themes. Plan how can you restrict them.

- Go through the tests as well and understand how the tests are setup.

- change only the prompts file and nothing else.

### Required packages

```
langchain
langchain-ollama
ollama
```

# Steps

Step 1: create a virtual environment:

```
python -m venv venv
```

Step 2:  install the packages:
```
pip install -r requirements.txt
```

Step 3:  update the prompts as required

Step 4: run code_translation.py
```
python code_translation.py --user-prompt-file prompts/user-prompt.txt --system-prompt-file prompts/system-prompt.txt
```

Step 5: run tests:

Go to `output_code_translation` folder. Then run:
```
python -m unittest discover -s test -v
```
