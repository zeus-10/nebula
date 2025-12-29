# 🌍 Making Nebula Global: PowerShell & Terminal Setup

## Method 1: PowerShell Function (Recommended for Windows)

### Step 1: Open PowerShell Profile

```powershell
# Check if profile exists
Test-Path $PROFILE

# If false, create it
New-Item -Path $PROFILE -Type File -Force

# Open in notepad
notepad $PROFILE
```

### Step 2: Add Nebula Function

Add this to your PowerShell profile:

```powershell
# Nebula CLI - WSL wrapper
function nebula {
    param(
        [Parameter(ValueFromRemainingArguments=$true)]
        [string[]]$Arguments
    )
    
    $wslCommand = "cd /home/abhinav/dev/nebula/client/cli && source /home/abhinav/dev/nebula/client/.venv/bin/activate && nebula $($Arguments -join ' ')"
    wsl -e bash -c $wslCommand
}
```

### Step 3: Reload Profile

```powershell
. $PROFILE
```

### Step 4: Test

```powershell
nebula ping
nebula list
```

**Now you can use `nebula` from anywhere in PowerShell!**

---

## Method 2: Batch File (Alternative for Windows)

### Step 1: Create Batch File

Create `C:\Users\abhin\nebula.bat`:

```batch
@echo off
wsl -e bash -c "cd /home/abhinav/dev/nebula/client/cli && source /home/abhinav/dev/nebula/client/.venv/bin/activate && nebula %*"
```

### Step 2: Add to PATH

```powershell
# Get current PATH
$env:Path

# Add to PATH permanently
[Environment]::SetEnvironmentVariable(
    "Path",
    [Environment]::GetEnvironmentVariable("Path", "User") + ";C:\Users\abhin",
    "User"
)
```

### Step 3: Test

```powershell
nebula ping
```

---

## Method 3: Linux Terminal (Make it Global)

### Step 1: Create Alias in .bashrc

```bash
# Edit your .bashrc
nano ~/.bashrc

# Add at the end:
alias nebula='cd /home/abhinav/dev/nebula/client/cli && source /home/abhinav/dev/nebula/client/.venv/bin/activate && nebula'
```

**Problem:** This changes directory. Better approach below ↓

### Step 2: Better Solution - Wrapper Script

Create `/usr/local/bin/nebula` (requires sudo):

```bash
sudo nano /usr/local/bin/nebula
```

Add this content:

```bash
#!/bin/bash
cd /home/abhinav/dev/nebula/client/cli
source /home/abhinav/dev/nebula/client/.venv/bin/activate
exec python -m src.main "$@"
```

Make it executable:

```bash
sudo chmod +x /usr/local/bin/nebula
```

### Step 3: Test

```bash
# Should work from anywhere now
cd ~
nebula ping

cd /tmp
nebula list
```

---

## Method 4: Symlink Approach (Linux)

### Step 1: Install Nebula Package Properly

```bash
cd /home/abhinav/dev/nebula/client/cli
source /home/abhinav/dev/nebula/client/.venv/bin/activate
pip install -e .
```

This should create a `nebula` executable in your venv's `bin/` directory.

### Step 2: Find the Executable

```bash
# Find where it was installed
which nebula
# Output: /home/abhinav/dev/nebula/client/.venv/bin/nebula
```

### Step 3: Create Symlink (System-Wide)

```bash
# Create symlink in /usr/local/bin
sudo ln -s /home/abhinav/dev/nebula/client/.venv/bin/nebula /usr/local/bin/nebula

# Test
nebula ping
```

**But wait!** This won't work if the venv isn't activated. We need a wrapper script instead.

---

## Method 5: Proper Wrapper Script (Best for Linux)

### Step 1: Create Wrapper Script

```bash
sudo nano /usr/local/bin/nebula
```

Add:

```bash
#!/bin/bash
# Nebula CLI Wrapper - Activates venv and runs CLI

VENV_DIR="/home/abhinav/dev/nebula/client/.venv"
CLI_DIR="/home/abhinav/dev/nebula/client/cli"

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Change to CLI directory (for .env.client)
cd "$CLI_DIR"

# Run nebula command
exec python -m src.main "$@"
```

### Step 2: Make Executable

```bash
sudo chmod +x /usr/local/bin/nebula
```

### Step 3: Test

```bash
cd ~
nebula ping
nebula list
nebula upload "/mnt/c/Users/abhin/Downloads/test.txt"
```

**Perfect! Now works from anywhere!**

---

## Method 6: Cross-Platform Script (Works Both Ways)

Create a script that detects the environment:

```bash
sudo nano /usr/local/bin/nebula
```

```bash
#!/bin/bash
# Nebula CLI - Cross-platform wrapper

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="/home/abhinav/dev/nebula/client/.venv"
CLI_DIR="/home/abhinav/dev/nebula/client/cli"

# Check if we're in WSL or native Linux
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    cd "$CLI_DIR"
    exec python -m src.main "$@"
else
    echo "Error: Nebula virtual environment not found at $VENV_DIR"
    exit 1
fi
```

```bash
sudo chmod +x /usr/local/bin/nebula
```

---

## Testing Your Setup

### Test from Different Locations

```bash
# From home directory
cd ~
nebula ping

# From temp directory
cd /tmp
nebula list

# From Windows Downloads (via WSL)
cd /mnt/c/Users/abhin/Downloads
nebula upload test.txt
```

### Test All Commands

```bash
nebula ping
nebula list
nebula status
nebula play 67
nebula download 67
nebula upload "/path/to/file"
```

---

## Troubleshooting

### "Command not found: nebula"

**Linux/WSL:**
```bash
# Check if script exists
ls -la /usr/local/bin/nebula

# Check if it's executable
file /usr/local/bin/nebula

# Check PATH
echo $PATH | grep /usr/local/bin
```

**PowerShell:**
```powershell
# Check if function exists
Get-Command nebula

# Check profile loaded
. $PROFILE
```

### "Module not found" or Import Errors

The wrapper script should handle venv activation. If not:

```bash
# Manually test the venv
source /home/abhinav/dev/nebula/client/.venv/bin/activate
cd /home/abhinav/dev/nebula/client/cli
nebula ping

# If that works, the wrapper script needs fixing
```

### PowerShell Function Not Working

```powershell
# Check WSL path is correct
wsl -e bash -c "cd /home/abhinav/dev/nebula/client/cli && pwd"

# Test the full command
wsl -e bash -c "cd /home/abhinav/dev/nebula/client/cli && source /home/abhinav/dev/nebula/client/.venv/bin/activate && nebula ping"
```

---

## Recommended Setup

**For Windows (PowerShell):**
- Use **Method 1** (PowerShell Function) - Cleanest, no PATH modifications needed

**For Linux/WSL:**
- Use **Method 5** (Wrapper Script) - Most reliable, works from anywhere

**For Both:**
- You can use both! PowerShell function for Windows, wrapper script for WSL terminal






