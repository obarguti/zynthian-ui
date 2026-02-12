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
            
            # Magnetic snap points at 0.00 and -50.00
            snap_threshold = 3.0  # cents within which to snap
            if abs(self.value - 0.0) < snap_threshold:
                self.value = 0.0
            elif abs(self.value - (-50.0)) < snap_threshold:
                self.value = -50.0
            
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
        """Clear current bank - mark all non-zero values to be cleared to 0.0"""
        current_bank = self.banks[self.select_bank_index]
        # Mark all non-zero values as dirty (to be cleared)
        for i in range(12):
            if current_bank[i] != 0.0:
                self.dirty[i] = 0.0

    def commit(self):
        """Apply dirty values to the banks array and clear dirty"""
        for idx, value in self.dirty.items():
            self.banks[self.select_bank_index][idx] = value
        self.dirty = {}

    def get_pending_values(self):
        """Return the selected bank with dirty values overlayed on top"""
        result = self.banks[self.select_bank_index].copy()
        for idx, value in self.dirty.items():
            result[idx] = value
        return result


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
        self.cancel_button = None
        self.save_button = None
        self.pending_bank_idx = None
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
        
        try:
            with open(self.microtuning_file, 'r') as f:
                data = json.load(f)
                self.state.banks = data.get('banks', [[0.0] * 12 for _ in range(4)])
                logging.info("Loaded microtuning banks from file")
        except FileNotFoundError:
            logging.info("Microtuning banks file not found, using default banks")
        except Exception as e:
            logging.warning(f"Failed to load microtuning banks: {e}, using defaults")

    def save_banks(self):
        """Show confirmation before saving banks"""
        self.zyngui.show_confirm(
            f"Save changes to Bank {self.state.select_bank_index + 1}?\n\nThis will overwrite the existing values.",
            self.do_save_banks
        )

    def do_save_banks(self):
        """Actually save banks to JSON file after confirmation"""
        try:
            self.state.commit()
            with open(self.microtuning_file, 'w') as f:
                json.dump({'banks': [[round(val, 2) for val in bank] for bank in self.state.banks]}, f, indent=2)
            self.update_button_states()
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
        """Sync all key widgets with current bank values from state (applying dirty overrides)"""
        pending_values = self.state.get_pending_values()
        for widget in self.key_widgets:
            widget.set_value(pending_values[widget.note_idx])

    def update_button_states(self):
        """Enable or disable cancel and save buttons based on dirty state"""
        if not self.cancel_button:
            self.cancel_button = next((btn for btn in self.buttonbar_button 
                                       if btn and hasattr(btn, 'cuia') and btn.cuia == 'cancel'), None)
        if not self.save_button:
            self.save_button = next((btn for btn in self.buttonbar_button 
                                     if btn and hasattr(btn, 'cuia') and btn.cuia == 'save'), None)
        
        state = tkinter.NORMAL if self.state.dirty else tkinter.DISABLED
        self.cancel_button.config(state=state)
        self.save_button.config(state=state)

    def clear_bank(self):
        """Clear the current bank"""
        self.state.clear()
        self.sync_key_widgets()
        self.update_button_states()
        logging.info(f"Cleared dirty content for Bank {self.state.select_bank_index + 1}")

    def cancel_banks(self):
        """Cancel all changes - discard unsaved changes and restore saved values"""
        self.state.cancel()
        # Restore widgets to saved bank values (not zero!)
        self.sync_key_widgets()
        self.update_button_states()
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
                                text=f"Bank {i + 1}",
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
        white_spacing = (available_w / 7) * 0.85  # Reduced spacing
        # Center the keyboard by calculating offset
        total_keyboard_width = 6 * white_spacing + px_w
        centering_offset = (available_w - total_keyboard_width) / 2
        start_x = padding + centering_offset
        
        pending_values = self.state.get_pending_values()

        # Lower row: whites (7 keys)
        white_y = self.center_frame.winfo_height() - px_h - 50
        white_notes = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
        for i, note in enumerate(white_notes):
            idx = NOTES.index(note)
            x = start_x + i * white_spacing
            widget = MicrotuningKeyWidget(self.center_frame, note, px_w, px_h, 
                                          value=pending_values[idx], 
                                          callback=lambda val, idx=idx: self.on_key_value_change(idx, val))
            widget.note_idx = idx
            widget.place(x=x, y=white_y)
            self.key_widgets.append(widget)

        # Upper row: blacks (5 keys), aligned with whites
        black_y = white_y - px_h - 40
        black_notes = ['C#', 'D#', 'F#', 'G#', 'A#']
        black_positions = [0.5, 1.5, 3.5, 4.5, 5.5]  # Between whites
        for j, (note, pos) in enumerate(zip(black_notes, black_positions)):
            idx = NOTES.index(note)
            x = start_x + pos * white_spacing
            widget = MicrotuningKeyWidget(self.center_frame, note, px_w, px_h, 
                                          value=pending_values[idx], 
                                          callback=lambda val, idx=idx: self.on_key_value_change(idx, val))
            widget.note_idx = idx
            widget.place(x=x, y=black_y)
            self.key_widgets.append(widget)

    def on_key_value_change(self, idx, value):
        # Only update dirty, not the saved banks
        self.state.dirty[idx] = value
        self.update_button_states()

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
            # Check if there are unsaved changes
            if self.state.dirty:
                self.pending_bank_idx = bank_idx
                self.zyngui.show_confirm(
                    f"You have unsaved changes in Bank {self.state.select_bank_index + 1}.\n\nSwitch to Bank {bank_idx + 1} and lose changes?",
                    self.do_select_bank
                )
            else:
                self.do_select_bank(bank_idx)

    def do_select_bank(self, bank_idx=None):
        """Actually select the bank after confirmation or if no dirty changes"""
        if bank_idx is None:
            bank_idx = self.pending_bank_idx
        self.state.select_bank_index = bank_idx
        self.state.dirty = {}  # Clear dirty when switching banks
        self.update_bank_button_states()
        self.sync_key_widgets()
        self.update_button_states()
        logging.info(f"Selected Bank {bank_idx + 1}")

    def show(self):
        super().show()
        if not self.keyboard_created:
            self.center_frame.update_idletasks()
            self.create_keyboard()
            self.keyboard_created = True
        self.update_button_states()
        self.set_select_path()

    def hide(self):
        super().hide()

    def set_select_path(self):
        self.select_path.set("Microtuning")

    def back_action(self):
        self.zyngui.show_screen("main_menu")

# ------------------------------------------------------------------------------