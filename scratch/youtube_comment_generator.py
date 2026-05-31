#!/usr/bin/env python3
"""
YouTube Comment Generator - Time & Work Reflection
An elegant terminal utility designed to generate thoughtful, four-sentence reflections 
about time and work-life balance, formatted perfectly for YouTube comments.
Features native macOS clipboard integration (pbcopy) and beautiful terminal cards.
"""

import os
import sys
import subprocess
from datetime import datetime

# Curated high-quality, relatable templates reflecting on time and work
COMMENT_TEMPLATES = [
    {
        "style": "Philosophical / Relatable (Recommended)",
        "sentences": [
            "Time moves in a quiet, relentless stream, yet we spend so much of it locked inside the daily grind of our jobs.",
            "It is easy to get lost in the endless tasks at work, but we must remember that our lives are defined by the moments of peace we find in between.",
            "Let’s not let the clock rule our spirits or let labor consume our entire sense of wonder.",
            "Keep breathing, keep creating, and remember to reclaim your hours whenever you can."
        ],
        "emoji": "🕰️"
    },
    {
        "style": "Mindful / Grounding",
        "sentences": [
            "We often treat our jobs like the center of the universe, forgetting that the clock never stops ticking for anyone.",
            "Work is what we do to live, not the reason we are alive.",
            "Taking a moment to pause and breathe is not a waste of time; it is how we remember who we are.",
            "Don't forget to look up from the screen today and appreciate the simple beauty of the passing hours."
        ],
        "emoji": "🌱"
    },
    {
        "style": "Motivating / Encouraging",
        "sentences": [
            "Every hour spent at work is an investment, but the greatest investment you can make is in your own peace of mind.",
            "The grind can feel overwhelming, but remember that you are far bigger than any job description.",
            "Time is our most precious currency, so make sure you are spending enough of it on what makes you happy.",
            "Keep pushing forward, but always protect your energy and make space for your own dreams."
        ],
        "emoji": "✨"
    }
]

def copy_to_clipboard(text: str) -> bool:
    """Copies text to the macOS clipboard using native pbcopy."""
    try:
        process = subprocess.Popen(
            ['pbcopy'], 
            stdin=subprocess.PIPE, 
            close_fds=True, 
            text=True
        )
        process.communicate(input=text)
        return process.returncode == 0
    except Exception:
        return False

def print_card(title: str, content: str, style_name: str, formatted_time: str):
    """Prints a beautiful, premium terminal card with the comment."""
    width = 70
    border = "═" * width
    divider = "─" * width
    
    print(f"\n\033[1;36m╔{border}╗\033[0m")
    print(f"\033[1;36m║\033[0m \033[1;37m{title.center(width - 2)}\033[0m \033[1;36m║\033[0m")
    print(f"\033[1;36m╠{divider}╣\033[0m")
    print(f"\033[1;36m║\033[0m \033[1;33mStyle:\033[0m {style_name:<{width - 10}} \033[1;36m║\033[0m")
    print(f"\033[1;36m║\033[0m \033[1;33mTime:\033[0m  {formatted_time:<{width - 10}} \033[1;36m║\033[0m")
    print(f"\033[1;36m╠{divider}╣\033[0m")
    
    # Split content by explicit newlines first, then wrap each segment
    lines = content.split('\n')
    for line in lines:
        if not line.strip():
            # Empty line, print an empty row with borders
            print(f"\033[1;36m║\033[0m  {'':<{width - 4}}  \033[1;36m║\033[0m")
            continue
            
        words = line.split(' ')
        current_line = []
        current_length = 0
        for word in words:
            if current_length + len(word) + 1 > width - 4:
                line_str = " ".join(current_line)
                print(f"\033[1;36m║\033[0m  {line_str:<{width - 4}}  \033[1;36m║\033[0m")
                current_line = [word]
                current_length = len(word)
            else:
                current_line.append(word)
                current_length += len(word) + 1
                
        if current_line:
            line_str = " ".join(current_line)
            print(f"\033[1;36m║\033[0m  {line_str:<{width - 4}}  \033[1;36m║\033[0m")
        
    print(f"\033[1;36m╚{border}╝\033[0m\n")

def main():
    print("\n\033[1;32m🌟 KENBUN YOUTUBE COMMENT GENERATOR 🌟\033[0m")
    print("Generate thoughtful reflections about time and work to leave on videos.\n")
    
    # Format current local time nicely
    now = datetime.now()
    # E.g., "1:46 PM (May 30, 2026)"
    formatted_time = now.strftime("%I:%M %p (%b %d, %Y)")
    
    print("Choose a comment style:")
    for idx, template in enumerate(COMMENT_TEMPLATES, 1):
        print(f"  \033[1;35m{idx}.\033[0m {template['style']}")
    
    try:
        choice = input("\nEnter number (default 1): ").strip()
        choice_idx = int(choice) - 1 if choice else 0
        if choice_idx < 0 or choice_idx >= len(COMMENT_TEMPLATES):
            choice_idx = 0
    except ValueError:
        choice_idx = 0
        
    selected = COMMENT_TEMPLATES[choice_idx]
    
    # Combine sentences into a beautiful 4-sentence paragraph
    paragraph = " ".join(selected["sentences"])
    emoji = selected["emoji"]
    
    # Create the final comment with signature and timestamp
    comment_text = (
        f"{paragraph}\n\n"
        f"{emoji} [{formatted_time}] — Written in the margins of the workday."
    )
    
    # Print the result
    print_card("YOUTUBE COMMENT READY", comment_text, selected["style"], formatted_time)
    
    # Attempt to copy to clipboard (macOS native pbcopy)
    copied = copy_to_clipboard(comment_text)
    if copied:
        print("\033[1;32m✔ SUCCESS: Comment automatically copied to your clipboard! Go ahead and paste it on YouTube.\033[0m\n")
    else:
        print("\033[1;33m⚠ Note: Clipboard copying failed. You can copy the comment text from the card above.\033[0m\n")

if __name__ == "__main__":
    main()
