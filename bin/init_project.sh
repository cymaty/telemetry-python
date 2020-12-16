#!/usr/bin/env bash

red=$'\e[1;31m'
green=$'\e[1;32m'
yellow=$'\e[1;33m'
blue=$'\e[1;34m'
magenta=$'\e[1;35m'
cyan=$'\e[1;36m'
reset=$'\e[0m'
bold=$'\e[1m'

function checking() {
  printf '%s' "${bold}$1${reset}"
}

function check_failed() {
  echo -ne "\r"
  tput cuf 60
  printf '%s\n' "[ ${red}FAILED${reset} ]"
}

function check_skip() {
  echo -ne "\r"
  tput cuf 60
  printf '%s\n' "[  ${yellow}SKIP*${reset} ]"
}

function check_ok() {
  echo -ne "\r"
  tput cuf 60
  printf '%s\n' "[   ${green}OK${reset}   ]"
}


function run_command() {
  local name="$1"
  local cmd="$2"
  local errmsg="$3"
  checking "$name"
  output=$((eval "$cmd") 2>&1)
  ret=$?

  if [ $ret -eq 0 ]; then
    check_ok
  elif [ $ret -eq 100 ]; then
    check_skip
  else
    check_failed
    echo ""
    echo "${red}${errmsg}${reset}"
    echo ""
    echo "${red}${output}${reset}"
    exit 1
  fi
}

EXPECTED_PYTHON_VERSION="$(cat .python-version)"

run_command "Checking Dev Environment is set up" \
  "[ -d "~/.alchemy/spark" ]" \
  "Is seems that the dev environment is not setup, did you run ./bin/update-dev-environment.sh to completion yet?"

run_command "Ensure coreutils is installed" \
  "brew install coreutils"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PROJECT_DIR="$(realpath "${SCRIPT_DIR}/../")"

run_command "Checking pyenv installed" \
  "which pyenv" \
  "pyenv not found!  Did you run the ./bin/update-dev-environment.sh script yet?"


run_command "Checking pyenv shell integration" \
  "(echo $PATH | grep pyenv/shims)" \
  "pyenv not initialized properly.  Did you run the ./bin/update-dev-environment.sh and update/reopen your shell?"

run_command "Ensure Python $EXPECTED_PYTHON_VERSION is available" "pyenv install -s"

eval "$(pyenv init -)"

# redirect stderr to stdout since python -V writes to that instead?
PYTHON_VERSION=$((python -V | head | awk '{print $2}') 2>&1)

run_command "Checking Python $EXPECTED_PYTHON_VERSION activated" \
  "[ \"$EXPECTED_PYTHON_VERSION\" == \"$PYTHON_VERSION\" ]" \
  "pyenv not working properly.  Expected Python $EXPECTED_PYTHON_VERSION but got $PYTHON_VERSION"

run_command "Creating local Python virtual environment in .venv" "python -m venv $PROJECT_DIR/.venv"

EXPECTED_PYTHON="$(realpath $PROJECT_DIR/.venv/bin/python)"
EXPECTED_PIP="$(realpath $PROJECT_DIR/.venv/bin/pip)"

run_command "Verifying virtual environment exists" \
  "[ -f \"$PROJECT_DIR/.venv/bin/activate\" ]" \
  "Could not find .venv/bin/activate"

. $PROJECT_DIR/.venv/bin/activate


run_command "Verifying virtual environment has python and pip" \
  "[ \"$(realpath "$(which python)")\" == \"$EXPECTED_PYTHON\" ] && [ \"$(realpath "$(which pip)")\" == \"$EXPECTED_PIP\" ]" \
  "Invalid python and/or pip in virtual environment"

run_command "Upgrading pip" \
  "pip install --upgrade pip"

run_command "Installing Python packages from python/requirements.txt" \
  "pip install -r $PROJECT_DIR/requirements-test.txt" \
  "Failed to install Python packages"

run_command "Installing project in editable mode" \
  "pip install -e $PROJECT_DIR" \
  "Failed to install project in editable mode"
  
run_command "Checking direnv" \
  "which direnv" \
  "direnv not found! Auto-activation will not be available"


echo "${green}Project initialized OK${reset}"
echo ""
echo "${blue}To ensure the project is activated in your current shell, run the following commands:${reset}"
echo ""
echo -e "${bold}\tdirenv reload${reset}"
echo ""
echo "${blue}NOTE: If direnv is working correctly, then subsequent shells opened in this project will have this virtual environment automatically activated.${reset}"


