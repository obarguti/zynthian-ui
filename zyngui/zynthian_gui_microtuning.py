#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Microtuning Class
#
# Copyright (C) 2024 Zynthian Team
#
# ******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
# ******************************************************************************

import tkinter
import logging
import os
import json

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base

# ------------------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------------------
NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
BLACK_KEYS_COLOR = "#2F2F2F"
WHITE_KEYS_COLOR = "#C0C0C0"
TUNING_RANGE = [-50, 50]
LABEL_SIZE = zynthian_gui_config.font_size

# ------------------------------------------------------------------------------
# Microtuning Key Widget Class
# ------------------------------------------------------------------------------
class MicrotuningKeyWidget(tkinter.Frame):
    def __init__(self, parent, name, px_w, px_h, value=0, callback=None, **kwargs):

        super().__init__(parent, bg=zynthian_gui_config.color_panel_bg, **kwargs)

        self.name = name
        self.callback = callback

        isBlack = len(name) > 1
        bg_color = WHITE_KEYS_COLOR if not isBlack else BLACK_KEYS_COLOR
        text_color = BLACK_KEYS_COLOR if not isBlack else WHITE_KEYS_COLOR

        # Create canvas
        self.canvas = tkinter.Canvas(self, width=px_w, height=px_h, 
                                     bg=bg_color,
                                     bd=0,
                                     highlightthickness=0,
                                     relief=tkinter.FLAT)
        self.canvas.pack()

        # Draw note text
        self.canvas.create_text(px_w // 2, px_h // 2, text=name, fill=text_color, 
                                font=(zynthian_gui_config.font_family, LABEL_SIZE))

        # Draw initial marker line
        self.marker_y = 0.5 * px_h
        self.marker = self.canvas.create_line(0, self.marker_y, px_w, self.marker_y, fill=zynthian_gui_config.color_on, width=4, tags="marker")

        # Bind to configure event to update marker when canvas is resized
        self.canvas.bind("<Configure>", self.on_configure)

        # Create label
        self.label = tkinter.Label(self, text="0.00", fg=WHITE_KEYS_COLOR, bg=zynthian_gui_config.color_panel_bg, 
                                   font=(zynthian_gui_config.font_family, LABEL_SIZE - 2))
        self.label.pack()

        # Set initial value and update marker position
        self.set_value(value)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<B1-Motion>", self.on_motion)

        self.press_event = None

    def get_value(self):
        return self.value

    def set_value(self, value):
        self.value = self._clamp(float(value), TUNING_RANGE[0], TUNING_RANGE[1])
        self.update_marker()
        self.label.config(text=f"{self.value:.2f}")

    def update_marker(self):
        height = self.canvas.winfo_height()
        val = (TUNING_RANGE[1] - self.value) / 100  # 0 at top (+50), 1 at bottom (-50)
        self.marker_y = val * height
        self.canvas.coords(self.marker, 0, self.marker_y, self.canvas.winfo_width(), self.marker_y)

    def on_press(self, event):
        self.press_event = event

    def on_release(self, event):
        self.press_event = None

    def _clamp(self, value, min_val, max_val):
        """Private helper function to clamp a value between min and max."""
        return max(min_val, min(max_val, value))

    def on_motion(self, event):
        if self.press_event:
            height = self.canvas.winfo_height()
            val = self._clamp(event.y / height, 0, 1)
            self.value = TUNING_RANGE[1] - (val * 100)
            self.update_marker()
            self.label.config(text=f"{self.value:.2f}")
            if self.callback:
                self.callback(self.value)

    def on_configure(self, event):
        self.update_marker()


# ------------------------------------------------------------------------------
# Microtuning State Class
# ------------------------------------------------------------------------------

class MicrotuningState:
    def __init__(self, banks=None, selected_bank=0):
        self.select_bank_index = selected_bank

        if banks is None:
            self.banks = [[0.0] * 12 for _ in range(4)]  # 4 banks, each with 12 floats
        else:
            self.banks = banks
        self.dirty = {}

    def cancel(self):
        """Delete the dirty content only - discard unsaved changes"""
        self.dirty = {}

    def clear(self):
        """Clear current bank - set non-zero values to 0.0 and mark as dirty"""
        current_bank = self.banks[self.select_bank_index]
        for i in range(12):
            if current_bank[i] != 0.0:
                current_bank[i] = 0.0
                self.dirty[i] = 0.0


# ------------------------------------------------------------------------------
# Zynthian Microtuning GUI Class
# ------------------------------------------------------------------------------

class zynthian_gui_microtuning(zynthian_gui_base):

    def __init__(self):
        self.buttonbar_config = [
            ("clear", 'Clear'),
            ("save", 'Save'),
            ("cancel", 'Cancel'),
            ("blank", '')
        ]

        super().__init__(has_backbutton=True)

        self.bank_buttons = []
        self.key_widgets = []
        self.keyboard_created = False
        self.state = MicrotuningState()
        self.load_banks()
        self.create_page_layout()
        self.create_bank_buttons()
        self.update_bank_button_states()

    def load_banks(self):
        """Load banks from JSON file if it exists"""
        self.my_data_dir = os.environ.get('ZYNTHIAN_MY_DATA_DIR', "/zynthian/zynthian-my-data")
        self.microtuning_dir = os.path.join(self.my_data_dir, "microtuning")
        os.makedirs(self.microtuning_dir, exist_ok=True)
        self.microtuning_file = os.path.join(self.microtuning_dir, "banks.json")
        
        if os.path.exists(self.microtuning_file):
            try:
                with open(self.microtuning_file, 'r') as f:
                    data = json.load(f)
                    if 'banks' in data:
                        self.state.banks = data['banks']
                        logging.info("Loaded microtuning banks from file")
                    else:
                        logging.warning("Microtuning file exists but has no 'banks' data, using defaults")
            except Exception as e:
                logging.warning(f"Failed to load microtuning banks: {e}, using defaults")
        else:
            logging.info("Microtuning banks file not found, using default banks (all zeros)")

    def save_banks(self):
        """Save banks to JSON file"""
        try:
            # Round all values to 2 decimal places
            rounded_banks = [[round(val, 2) for val in bank] for bank in self.state.banks]
            data = {'banks': rounded_banks}
            with open(self.microtuning_file, 'w') as f:
                json.dump(data, f, indent=2)
            # Clear dirty after successful save
            self.state.dirty = {}
            self.update_cancel_button_state()
            logging.info("Saved microtuning banks to file")
        except Exception as e:
            logging.error(f"Failed to save microtuning banks: {e}")

    def cb_button_release(self, event):
        cuia = event.widget.cuia
        if cuia == "clear":
            self.clear_bank()
        elif cuia == "save":
            self.save_banks()
        elif cuia == "cancel":
            self.cancel_banks()
        else:
            super().cb_button_release(event)

    def sync_key_widgets(self):
        """Sync all key widgets with current bank values from state"""
        for widget in self.key_widgets:
            idx = NOTES.index(widget.name)
            widget.set_value(self.state.banks[self.state.select_bank_index][idx])

    def update_cancel_button_state(self):
        """Enable or disable cancel button based on dirty state"""
        # Find cancel button in buttonbar_button list
        cancel_button = None
        for button in self.buttonbar_button:
            if button and hasattr(button, 'cuia') and button.cuia == 'cancel':
                cancel_button = button
                break
        
        if cancel_button:
            if self.state.dirty:
                # Enable button
                cancel_button.config(state=tkinter.NORMAL)
            else:
                # Disable and gray out button
                cancel_button.config(state=tkinter.DISABLED)

    def clear_bank(self):
        """Clear the current bank"""
        self.state.clear()
        self.sync_key_widgets()
        self.update_cancel_button_state()
        logging.info(f"Cleared dirty content for Bank {self.state.select_bank_index + 1}")

    def cancel_banks(self):
        """Cancel all changes - discard unsaved changes"""
        self.state.cancel()
        for widget in self.key_widgets:
            idx = NOTES.index(widget.name)
            widget.set_value(0.0)
        self.update_cancel_button_state()
        logging.info("Cancelled all bank changes")
        
    def create_page_layout(self):
        # Main content area
        self.main_frame.configure(bg=zynthian_gui_config.color_panel_bg)
        
        # Configure grid following the layout pattern
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=3, uniform="main")
        self.main_frame.columnconfigure(1, weight=1, uniform="main")
        
        # Large canvas for keyboard visualization (center)
        self.center_frame = tkinter.Frame(self.main_frame,
                                          bg=zynthian_gui_config.color_panel_bg)
        
        self.center_frame.rowconfigure(0, weight=1)
        self.center_frame.columnconfigure(0, weight=1)
        
        # Right side frame for bank selector buttons
        self.right_frame = tkinter.Frame(self.main_frame,
                                         bg=zynthian_gui_config.color_panel_bg)
        
        self.center_frame.grid(row=0, column=0, rowspan=4, padx=(0, 2), sticky='news')
        self.right_frame.grid(row=0, column=1, rowspan=4, sticky='news')

        # Add bottom border (1px black)
        bottom_border = tkinter.Frame(self.main_frame, bg=BLACK_KEYS_COLOR, height=2)
        bottom_border.pack(side='bottom', fill='x')

        # Add left border (1px black) to right_frame
        left_border = tkinter.Frame(self.right_frame, bg=BLACK_KEYS_COLOR, width=2)
        left_border.pack(side='left', fill='y')

    def create_bank_buttons(self):
        # Create 4 bank selector buttons on the right
        for i in range(4):
            btn_frame = tkinter.Frame(self.right_frame, bg=zynthian_gui_config.color_panel_bg)
            btn_frame.pack(fill=tkinter.BOTH, expand=True, pady=1)
            
            # Top border
            top_border = tkinter.Frame(btn_frame, bg=BLACK_KEYS_COLOR, height=1)
            top_border.pack(fill='x', side='top')
            
            btn = tkinter.Button(btn_frame,
                                text=f"{i + 1}",
                                font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size),
                                bg=zynthian_gui_config.color_panel_bg,
                                fg=zynthian_gui_config.color_tx,
                                activebackground=zynthian_gui_config.color_panel_bg,
                                activeforeground=zynthian_gui_config.color_tx,
                                bd=0,
                                highlightthickness=0,
                                relief=tkinter.FLAT,
                                command=lambda idx=i: self.select_bank(idx))
            btn.pack(fill=tkinter.BOTH, expand=True, padx=0, pady=0)
            self.bank_buttons.append(btn)
    
    def get_key_sizes(self):
        """Helper to measure pixel sizes for keys (same for white and black)"""
        key_width = 3
        key_height = 8

        # Measure key size (same for both white and black)
        dummy_key = tkinter.Button(
            self.center_frame, text="C", width=key_width, height=key_height,
            font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size)
        )
        dummy_key.update_idletasks()
        px_w = dummy_key.winfo_reqwidth()
        px_h = dummy_key.winfo_reqheight()
        dummy_key.destroy()

        return px_w, px_h

    def create_keyboard(self):
        self.center_frame.update_idletasks()
        px_w, px_h = self.get_key_sizes()
        padding = 10
        center_w = self.center_frame.winfo_width()
        available_w = center_w - 2 * padding
        white_spacing = available_w / 7
        start_x = padding

        # Lower row: whites (7 keys)
        white_y = self.center_frame.winfo_height() - px_h - 30
        white_notes = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
        for i, note in enumerate(white_notes):
            idx = NOTES.index(note)
            x = start_x + i * white_spacing
            widget = MicrotuningKeyWidget(self.center_frame, note, px_w, px_h, 
                                          value=self.state.banks[self.state.select_bank_index][idx], 
                                          callback=lambda val, idx=idx: self.on_key_value_change(idx, val))
            widget.place(x=x, y=white_y)
            self.key_widgets.append(widget)

        # Upper row: blacks (5 keys), aligned with whites
        black_y = white_y - px_h - 40
        black_notes = ['C#', 'D#', 'F#', 'G#', 'A#']
        black_positions = [0.5, 1.5, 3.5, 4.5, 5.5]  # Between whites
        for j, (note, pos) in enumerate(zip(black_notes, black_positions)):
            idx = NOTES.index(note)
            x = start_x + pos * white_spacing - px_w / 2
            widget = MicrotuningKeyWidget(self.center_frame, note, px_w, px_h, 
                                          value=self.state.banks[self.state.select_bank_index][idx], 
                                          callback=lambda val, idx=idx: self.on_key_value_change(idx, val))
            widget.place(x=x, y=black_y)
            self.key_widgets.append(widget)

    def on_key_value_change(self, idx, value):
        self.state.banks[self.state.select_bank_index][idx] = value
        self.state.dirty[idx] = value
        self.update_cancel_button_state()

    def update_bank_button_states(self):
        """Update the visual state of bank buttons (e.g., highlight selected)"""
        for i, btn in enumerate(self.bank_buttons):
            if i == self.state.select_bank_index:
                btn.config(bg="red", fg="white", activebackground="red", activeforeground="white")
            else:
                btn.config(bg=zynthian_gui_config.color_panel_bg, fg=zynthian_gui_config.color_tx,
                          activebackground=zynthian_gui_config.color_panel_bg, activeforeground=zynthian_gui_config.color_tx)
        self.update_idletasks()

    def select_bank(self, bank_idx):
        """Select a bank (0-3) and update UI"""
        if bank_idx != self.state.select_bank_index:
            self.state.select_bank_index = bank_idx
            self.update_bank_button_states()
            self.sync_key_widgets()
            logging.info(f"Selected Bank {bank_idx + 1}")

    def show(self):
        super().show()
        if not self.keyboard_created:
            self.center_frame.update_idletasks()
            self.create_keyboard()
            self.keyboard_created = True
        self.update_cancel_button_state()
        self.set_select_path()

    def hide(self):
        super().hide()

    def set_select_path(self):
        self.select_path.set("Microtuning")

    def back_action(self):
        self.zyngui.show_screen("main_menu")

# ------------------------------------------------------------------------------