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
import tkinter.font as tkfont
import logging
import os
import json
from threading import Timer

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base
import zynautoconnect
from zyncoder.zyncore import lib_zyncore

# ------------------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------------------
NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
BLACK_KEYS_COLOR = "#2F2F2F"
WHITE_KEYS_COLOR = "#C0C0C0"
TUNING_RANGE = [-50, 50]
TUNING_UPDATE_DELAY = 500  # Milliseconds to wait before applying tuning to engine
MS_TO_SECONDS = 1000.0

# ------------------------------------------------------------------------------
# Microtuning Key Widget Class
# ------------------------------------------------------------------------------
class MicrotuningKeyWidget(tkinter.Frame):
    def __init__(self, parent, name, px_w, px_h, value=0, callback=None, **kwargs):
        cfg = zynthian_gui_config
        super().__init__(parent, bg=cfg.color_panel_bg, **kwargs)

        self.name = name
        self.callback = callback

        is_black = len(name) > 1
        bg_color = WHITE_KEYS_COLOR if not is_black else BLACK_KEYS_COLOR
        text_color = BLACK_KEYS_COLOR if not is_black else WHITE_KEYS_COLOR
        font_size = cfg.font_size
        font_family = cfg.font_family

        def linespace(size):
            return tkfont.Font(family=font_family, size=size).metrics('linespace')

        value_font_size = int(0.75 * font_size) if not is_black else int(0.7 * font_size)
        value_text_height = linespace(int(0.75 * font_size))
        self.marker_half_h = max(1, linespace(font_size) // 8)
        self.key_height = px_h - value_text_height

        # Create canvas
        self.canvas = tkinter.Canvas(self, width=px_w, height=px_h,
                                     bg=cfg.color_panel_bg, bd=0,
                                     highlightthickness=0, relief=tkinter.FLAT)
        self.canvas.pack(fill='both')

        center_x = px_w // 2
        mid_y = self.key_height // 2

        self.key_rect = self.canvas.create_rectangle(0, 0, px_w, self.key_height, fill=bg_color, outline=bg_color)

        # 1px side and bottom borders for white keys
        if not is_black:
            self.canvas.create_line(0, 0, 0, self.key_height, fill=BLACK_KEYS_COLOR, width=1)
            self.canvas.create_line(px_w - 1, 0, px_w - 1, self.key_height, fill=BLACK_KEYS_COLOR, width=1)

        # Note name, marker line, neutral rect, value text
        self.note_text   = self.canvas.create_text(center_x, mid_y, text=name, fill=text_color, font=(font_family, font_size))
        self.marker_y    = mid_y
        self.marker      = self.canvas.create_line(0, mid_y, px_w, mid_y, fill=cfg.color_on, width=self.marker_half_h * 2, stipple="gray50", tags="marker")
        self.neutral_rect = self.canvas.create_rectangle(
            0, mid_y - self.marker_half_h, px_w, mid_y + self.marker_half_h,
            fill=cfg.color_on, outline="", stipple="gray50", tags="neutral_rect"
        )
        self.value_text  = self.canvas.create_text(center_x, px_h - value_text_height // 2, text="0.0",
                                fill=cfg.color_tx, font=(font_family, value_font_size))

        self.canvas.bind("<Configure>", self.on_configure)
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
        self.canvas.itemconfig(self.value_text, text=f"{self.value:.1f}")

    def update_marker(self):
        val = (TUNING_RANGE[1] - self.value) / 100  # 0 at top (+50), 1 at bottom (-50)
        self.marker_y = self._clamp(val * self.key_height, self.marker_half_h, self.key_height - self.marker_half_h + 1)
        w = self.canvas.winfo_width()
        self.canvas.coords(self.marker, 0, self.marker_y, w, self.marker_y)
        neutral_y = 0.5 * self.key_height
        self.canvas.coords(self.neutral_rect, 0, neutral_y - self.marker_half_h, w, neutral_y + self.marker_half_h)
        if self.value == 0.0:
            self.canvas.itemconfig(self.marker, state=tkinter.HIDDEN)
            self.canvas.itemconfig(self.neutral_rect, state=tkinter.NORMAL)
        else:
            self.canvas.itemconfig(self.marker, state=tkinter.NORMAL)
            self.canvas.itemconfig(self.neutral_rect, state=tkinter.HIDDEN)

    def on_press(self, event):
        self.press_event = event
        self.press_start_y = event.y
        self.press_start_value = self.value

    def on_release(self, event):
        self.press_event = None

    def _clamp(self, value, min_val, max_val):
        """Private helper function to clamp a value between min and max."""
        return max(min_val, min(max_val, value))

    def on_motion(self, event):
        if self.press_event:
            delta_y = event.y - self.press_start_y
            delta_cents = -(delta_y / self.key_height) * 100
            self.value = self._clamp(self.press_start_value + delta_cents, TUNING_RANGE[0], TUNING_RANGE[1])
            
            # Magnetic snap points at 0.00 and -50.00
            snap_threshold = 3.0  # cents within which to snap
            if abs(self.value - 0.0) < snap_threshold:
                self.value = 0.0
            elif abs(self.value - (-50.0)) < snap_threshold:
                self.value = -50.0
            
            self.update_marker()
            self.canvas.itemconfig(self.value_text, text=f"{self.value:.1f}")
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
        self.update_timer = None  # Timer for debouncing engine updates
        self.fluidsynth_engine = None  # Cached FluidSynth engine instance
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
        except FileNotFoundError:
            pass
        except Exception as e:
            logging.warning(f"Failed to load microtuning banks: {e}, using defaults")

    def save_banks(self):
        """Show confirmation before saving banks"""
        self.state.commit()  # Commit immediately when user clicks save
        self.zyngui.show_confirm(
            f"Save changes to Bank {self.state.select_bank_index + 1}?\\n\\nThis will overwrite the existing values.",
            self.do_save_banks
        )

    def do_save_banks(self, params=None):
        """Actually save banks to JSON file after confirmation"""
        try:
            with open(self.microtuning_file, 'w') as f:
                json.dump({'banks': [[round(val, 2) for val in bank] for bank in self.state.banks]}, f, indent=2)
            self.update_button_states()
            # Apply the saved tuning to engine
            self.apply_tuning_to_engine()
        except Exception as e:
            logging.error(f"Failed to save microtuning banks: {e}")
            import traceback
            logging.error(traceback.format_exc())

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

    def cancel_banks(self):
        """Cancel all changes - discard unsaved changes and restore saved values"""
        self.state.cancel()
        # Restore widgets to saved bank values (not zero!)
        self.sync_key_widgets()
        self.update_button_states()
        
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
        
        self.center_frame.grid(row=0, column=0, rowspan=4, sticky='news')
        self.right_frame.grid(row=0, column=1, rowspan=4, sticky='news')

        # Add left border to right_frame
        right_left_border = tkinter.Frame(self.right_frame, bg="black", width=2)
        right_left_border.pack(side='left', fill='y')

        # Add bottom border (1px black)
        bottom_border = tkinter.Frame(self.main_frame, bg="black", height=2)
        bottom_border.pack(side='bottom', fill='x')

    def create_bank_buttons(self):
        # Create 4 bank selector buttons on the right
        for i in range(4):
            btn_frame = tkinter.Frame(self.right_frame, bg=zynthian_gui_config.color_panel_bg)
            btn_frame.pack(fill=tkinter.BOTH, expand=True, pady=0)
            
            # Top border
            top_border = tkinter.Frame(btn_frame, bg="black", height=1)
            top_border.pack(fill='x', side='top')
            
            # Bottom border
            bottom_border = tkinter.Frame(btn_frame, bg="black", height=1)
            bottom_border.pack(fill='x', side='bottom')
            
            btn = tkinter.Button(btn_frame,
                                text=f"Bank {i + 1}",
                                font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size),
                                bg=zynthian_gui_config.color_panel_bg,
                                fg=zynthian_gui_config.color_tx,
                                activebackground=zynthian_gui_config.color_panel_bg,
                                activeforeground=zynthian_gui_config.color_tx,
                                bd=0,
                                highlightthickness=0,
                                relief=tkinter.FLAT)
            btn.bind('<ButtonRelease-1>', lambda event, idx=i: self.select_bank(idx))
            btn.pack(fill=tkinter.BOTH, expand=True, padx=0, pady=0)
            self.bank_buttons.append(btn)
    
    def get_key_sizes(self, parent=None):
        """Calculate key sizes based on parent frame type"""
        if parent is None:
            parent = self.center_frame
        
        # Get parent frame dimensions
        parent.update_idletasks()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        
        # Key height: occupy entire parent height
        key_height = parent_h
        
        # Key width: depends on which panel
        if parent == self.top_frame:
            # Top panel (black keys): divide by 12
            key_width = parent_w // 12
        elif parent == self.bottom_frame:
            # Bottom panel (white keys): fill entire width by distributing pixels
            key_width = parent_w // 7  # floor division ensures 7 keys always fit within frame width
        else:
            # Fallback
            key_width = parent_w // 7
        
        return key_width, key_height

    def create_keyboard(self):
        self.center_frame.update_idletasks()

        # Configure center_frame for two rows (top and bottom halves)
        self.center_frame.rowconfigure(0, weight=1)
        self.center_frame.rowconfigure(1, weight=1)
        self.center_frame.columnconfigure(0, weight=1)

        # 5% relative padding on all sides - fully responsive to any screen size
        pad = 0.05

        # Create top frame for black keys (top half minus outer padding)
        self.top_frame = tkinter.Frame(self.center_frame, bg=zynthian_gui_config.color_panel_bg)
        self.top_frame.place(relx=pad, rely=pad, relwidth=1 - 2 * pad, relheight=0.5 - pad)

        # Create bottom frame for white keys (bottom half minus outer padding)
        self.bottom_frame = tkinter.Frame(self.center_frame, bg=zynthian_gui_config.color_panel_bg)
        self.bottom_frame.place(relx=pad, rely=0.5, relwidth=1 - 2 * pad, relheight=0.5 - pad)

        # Update layout to get frame dimensions
        self.center_frame.update_idletasks()

        frame_w = self.top_frame.winfo_width()
        top_key_h = self.top_frame.winfo_height()
        bottom_key_h = self.bottom_frame.winfo_height()

        # White key width drives everything
        ww = frame_w // 7
        # Black key width: 67% of white key width
        bw = round(0.67 * ww)

        # Precompute white key positions using sub-pixel-accurate rounding
        white_xs = [round(i * frame_w / 7) for i in range(7)]
        white_ws = [round((i + 1) * frame_w / 7) - round(i * frame_w / 7) for i in range(7)]

        # Chromatic index → white key slot index (for white notes only)
        chrom_to_white = {0: 0, 2: 1, 4: 2, 5: 3, 7: 4, 9: 5, 11: 6}

        # Black key chromatic index → index of the white key to its RIGHT (boundary anchor)
        black_boundaries = {1: 1, 3: 2, 6: 4, 8: 5, 10: 6}

        pending_values = self.state.get_pending_values()

        # Bottom frame: white keys at sub-pixel-accurate positions
        white_notes = [(idx, note) for idx, note in enumerate(NOTES) if len(note) == 1]
        for white_idx, (idx, note) in enumerate(white_notes):
            x = white_xs[white_idx]
            w = white_ws[white_idx]
            widget = MicrotuningKeyWidget(self.bottom_frame, note, w, bottom_key_h,
                                          value=pending_values[idx],
                                          callback=lambda val, idx=idx: self.on_key_value_change(idx, val))
            widget.note_idx = idx
            widget.place(x=x, y=0, width=w, height=bottom_key_h)
            self.key_widgets.append(widget)

        # Top frame: white fillers first (placed before black keys so black keys render on top)
        for chrom_idx, white_idx in chrom_to_white.items():
            x = white_xs[white_idx]
            w = white_ws[white_idx]
            filler = tkinter.Canvas(self.top_frame, bg=WHITE_KEYS_COLOR, bd=0, highlightthickness=0, relief=tkinter.FLAT)
            filler.place(x=x, y=0, width=w, height=top_key_h)
            filler.create_line(0, 0, 0, top_key_h, fill=BLACK_KEYS_COLOR, width=1)
            filler.create_line(w - 1, 0, w - 1, top_key_h, fill=BLACK_KEYS_COLOR, width=1)

        # Top frame: black key widgets on top, centered at white key boundaries
        for chrom_idx, right_white_idx in black_boundaries.items():
            note = NOTES[chrom_idx]
            boundary_x = white_xs[right_white_idx]
            x = boundary_x - bw // 2
            widget = MicrotuningKeyWidget(self.top_frame, note, bw, top_key_h,
                                          value=pending_values[chrom_idx],
                                          callback=lambda val, idx=chrom_idx: self.on_key_value_change(idx, val))
            widget.note_idx = chrom_idx
            widget.place(x=x, y=0, width=bw, height=top_key_h)
            self.key_widgets.append(widget)

    def on_key_value_change(self, idx, value):
        # Only update dirty, not the saved banks
        self.state.dirty[idx] = value
        self.update_button_states()
        
        # Cancel any pending tuning update
        if self.update_timer:
            self.update_timer.cancel()
        
        # Schedule a new tuning update after debounce delay
        self.update_timer = Timer(TUNING_UPDATE_DELAY / MS_TO_SECONDS, self.apply_tuning_to_engine)
        self.update_timer.start()

    def refresh_fluidsynth_engine(self):
        """Scan all chains and cache a single FluidSynth engine instance"""
        self.fluidsynth_engine = None
        try:
            from zyngine.zynthian_engine_fluidsynth import zynthian_engine_fluidsynth
            
            chain_manager = self.zyngui.chain_manager
            for chain_id, chain in chain_manager.chains.items():
                for processor in chain.get_processors():
                    if isinstance(processor.engine, zynthian_engine_fluidsynth):
                        # Found one - that's all we need since there's only one FS process
                        self.fluidsynth_engine = processor.engine
                        return
        except Exception as e:
            logging.error(f"Error scanning for FluidSynth engine: {e}")

    def apply_tuning_to_engine(self):
        """
        Translates the current bank values into FluidSynth tuning commands
        and sends them directly to the FluidSynth engine.
        Since there's only one FluidSynth process, we only need to configure it once.
        """
        offsets = self.state.get_pending_values()
        engine = self.fluidsynth_engine
        
        try:
            # Create tuning (bank 0, program 0) - correct FluidSynth syntax
            engine.proc_cmd("tuning Microtuning 0 0")
            
            # Apply tuning to all 12 notes across all octaves
            # FluidSynth uses MIDI note numbers: 0-127
            # We apply the offsets to each note within the chromatic scale
            for octave in range(11):  # Octaves 0-10 cover 0-127
                for note_offset_idx, cents_offset in enumerate(offsets):
                    midi_note = octave * 12 + note_offset_idx
                    if midi_note <= 127:
                        # FluidSynth tune command: tune <bank> <prog> <key> <pitch>
                        # Pitch = MIDI note * 100 + cents_offset
                        pitch = midi_note * 100.0 + cents_offset
                        engine.proc_cmd(f"tune 0 0 {midi_note} {pitch}")
            
            # Apply tuning to all MIDI channels (0-15) - correct FluidSynth syntax
            for chan in range(16):
                engine.proc_cmd(f"settuning {chan} 0 0")
            
        except Exception as e:
            logging.error(f"Error applying tuning to FluidSynth: {e}")


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
        # Apply newly selected bank's tuning immediately
        self.apply_tuning_to_engine()

    def show(self):
        super().show()
        if not self.keyboard_created:
            self.center_frame.update_idletasks()
            self.create_keyboard()
            self.keyboard_created = True
        self.update_button_states()
        self.set_select_path()
        # Scan for and cache FluidSynth engine, then apply current tuning
        self.refresh_fluidsynth_engine()
        self.apply_tuning_to_engine()

    def hide(self):
        super().hide()

    def set_select_path(self):
        self.select_path.set("Microtuning")

    def back_action(self):
        self.zyngui.show_screen("main_menu")

# ------------------------------------------------------------------------------