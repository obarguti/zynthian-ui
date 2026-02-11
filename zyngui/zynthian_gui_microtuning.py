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

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_base import zynthian_gui_base

# ------------------------------------------------------------------------------
# Zynthian Microtuning GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_microtuning(zynthian_gui_base):

    def __init__(self):
        self.buttonbar_config = [
            ("clear", 'Clear'),
            ("save", 'Save'),
            ("reset", 'Reset'),
            ("blank", 'Blank')
        ]

        super().__init__(has_backbutton=True)

        # Track which scale is selected (0-3)
        self.selected_scale = 0
        self.scale_buttons = []
        self.note_canvases = []  # Store note canvases for the keyboard
        self.note_map = {}  # canvas to note
        self.slider_press_event = None
        self.notes = ['C', 'D', 'E', 'F', 'G', 'A', 'B', 'C#', 'D#', 'F#', 'G#', 'A#']
        self.tunings = {i: {note: 0.0 for note in self.notes} for i in range(4)}  # 4 scales, note: float cents
        self.cents_labels = []  # Labels for cents values

        # Main content area
        self.main_frame.configure(bg=zynthian_gui_config.color_panel_bg)
        
        # Configure grid following the layout pattern
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=3, uniform="main")
        self.main_frame.columnconfigure(1, weight=1, uniform="main")
        
        # Large canvas for keyboard visualization (center)
        self.canvas_frame = tkinter.Frame(self.main_frame,
                                          bg=zynthian_gui_config.color_panel_bg)
        
        # Right side frame for scale selector buttons
        self.right_frame = tkinter.Frame(self.main_frame,
                                         bg=zynthian_gui_config.color_panel_bg)
        
        self.canvas_frame.grid(row=0, column=0, rowspan=4, padx=(0, 2), sticky='news')
        self.right_frame.grid(row=0, column=1, rowspan=4, sticky='news')

        # Add bottom border (1px black)
        bottom_border = tkinter.Frame(self.main_frame, bg='black', height=2)
        bottom_border.pack(side='bottom', fill='x')

        # Add left border (1px black) to right_frame
        left_border = tkinter.Frame(self.right_frame, bg='black', width=2)
        left_border.pack(side='left', fill='y')

        # Create the piano-style keyboard layout
        self.create_keyboard()

        # Create 4 scale selector buttons on the right
        for i in range(4):
            btn_frame = tkinter.Frame(self.right_frame, bg=zynthian_gui_config.color_panel_bg)
            btn_frame.pack(fill=tkinter.BOTH, expand=True, pady=1)
            
            # Top border
            top_border = tkinter.Frame(btn_frame, bg='black', height=1)
            top_border.pack(fill='x', side='top')
            
            btn = tkinter.Button(btn_frame,
                                text=f"Scale {i+1}",
                                font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size),
                                bg=zynthian_gui_config.color_panel_bg,
                                fg=zynthian_gui_config.color_tx,
                                activebackground=zynthian_gui_config.color_panel_bg,
                                activeforeground=zynthian_gui_config.color_tx,
                                bd=0,
                                highlightthickness=0,
                                relief=tkinter.FLAT,
                                command=lambda idx=i: self.select_scale(idx))
            btn.pack(fill=tkinter.BOTH, expand=True, padx=0, pady=0)
            self.scale_buttons.append(btn)

        # Set the first button as selected by default
        self.update_scale_button_states()

    def create_keyboard(self):
        """Create a piano-style keyboard with 12 notes (2 rows interlocked)"""
        white_width = 3
        white_height = 8
        black_width = 3
        black_height = 7

        self.canvas_frame.update_idletasks()
        key_gap = 2

        # Measure pixel widths/heights
        dummy_white = tkinter.Button(
            self.canvas_frame, text="C", width=white_width, height=white_height,
            font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size)
        )
        dummy_white.update_idletasks()
        white_px_w = dummy_white.winfo_reqwidth()
        white_px_h = dummy_white.winfo_reqheight()
        dummy_white.destroy()

        dummy_black = tkinter.Button(
            self.canvas_frame, text="C#", width=black_width, height=black_height,
            font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size)
        )
        dummy_black.update_idletasks()
        black_px_w = dummy_black.winfo_reqwidth()
        black_px_h = dummy_black.winfo_reqheight()
        dummy_black.destroy()

        white_notes = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
        black_map = [(0, 'C#'), (1, 'D#'), (3, 'F#'), (4, 'G#'), (5, 'A#')]

        # Container centered in canvas_frame
        extra_top = 0  # No extra top space
        extra_bottom = 25  # Space below for labels
        label_space = 15  # Space between black and white for black labels
        total_w = 7 * white_px_w + 6 * key_gap
        total_h = white_px_h + black_px_h + label_space + extra_bottom
        self.keyboard_frame = tkinter.Frame(self.canvas_frame, bg=zynthian_gui_config.color_panel_bg,
                                            width=total_w, height=total_h)
        self.keyboard_frame.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.keyboard_frame.pack_propagate(False)

        # Precompute x positions of white keys
        white_x = [i * (white_px_w + key_gap) for i in range(7)]

        # White keys
        white_y = black_px_h + label_space
        for i, note in enumerate(white_notes):
            canvas = tkinter.Canvas(
                self.keyboard_frame,
                width=white_px_w,
                height=white_px_h,
                bg="white",
                bd=1,
                highlightthickness=0,
                relief=tkinter.RAISED
            )
            canvas.place(x=white_x[i], y=white_y, width=white_px_w, height=white_px_h)
            # Draw marker line (horizontal, initially at center)
            marker_y = 0.5 * white_px_h
            canvas.create_line(0, marker_y, white_px_w, marker_y, fill='red', width=2, tags="marker")
            # Draw note text
            canvas.create_text(white_px_w // 2, white_px_h // 2 - 5, text=note, fill="black", font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size))
            canvas.bind("<ButtonPress-1>", lambda e, idx=i: self.on_slider_press(e, idx))
            canvas.bind("<ButtonRelease-1>", self.on_slider_release)
            canvas.bind("<B1-Motion>", lambda e, idx=i: self.on_slider_motion(e, idx))
            self.note_canvases.append(canvas)
            
            # Label under white key
            label = tkinter.Label(self.keyboard_frame, text="0", fg="white", bg=zynthian_gui_config.color_panel_bg, 
                                  font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size))
            label.place(x=white_x[i] + white_px_w // 2, y=white_y + white_px_h, anchor="n")
            self.cents_labels.append(label)

        # Black keys
        black_y = 0
        for j, (left_i, note) in enumerate(black_map):
            boundary_center = white_x[left_i] + white_px_w + (key_gap / 2.0)
            bx = int(round(boundary_center - (black_px_w / 2.0)))

            canvas = tkinter.Canvas(
                self.keyboard_frame,
                width=black_px_w,
                height=black_px_h,
                bg=zynthian_gui_config.color_panel_bd,
                bd=0,
                highlightthickness=0,
                relief=tkinter.FLAT
            )
            canvas.place(x=bx, y=black_y, width=black_px_w, height=black_px_h)
            # Draw marker line (horizontal, initially at center)
            marker_y = 0.5 * black_px_h
            canvas.create_line(0, marker_y, black_px_w, marker_y, fill='red', width=2, tags="marker")
            # Draw note text
            canvas.create_text(black_px_w // 2, black_px_h // 2 - 5, text=note, fill=zynthian_gui_config.color_tx, font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size))
            idx = 7 + j  # White keys 0-6, black 7-11
            canvas.bind("<ButtonPress-1>", lambda e, idx=idx: self.on_slider_press(e, idx))
            canvas.bind("<ButtonRelease-1>", self.on_slider_release)
            canvas.bind("<B1-Motion>", lambda e, idx=idx: self.on_slider_motion(e, idx))
            self.note_canvases.append(canvas)
            
            # Label under black key
            label = tkinter.Label(self.keyboard_frame, text="0", fg="white", bg=zynthian_gui_config.color_panel_bg, 
                                  font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size))
            label.place(x=bx + black_px_w // 2, y=black_y + black_px_h, anchor="n")
            self.cents_labels.append(label)

    def note_pressed(self, note):
        """Handle note button press"""
        logging.info(f"Note pressed: {note} on Scale {self.selected_scale + 1}")
        # TODO: Add microtuning adjustment logic here

    def select_scale(self, scale_idx):
        """Select a scale tab (0-3) and update UI"""
        if scale_idx != self.selected_scale:
            self.selected_scale = scale_idx
            self.update_scale_button_states()
            self.update_canvas_display()
            logging.info(f"Selected Scale {scale_idx + 1}")

    def update_scale_button_states(self):
        for i, btn in enumerate(self.scale_buttons):
            if i == self.selected_scale:
                on_bg = zynthian_gui_config.color_ctrl_bg_on
                btn.config(
                    bg=on_bg,
                    activebackground=on_bg,   # <-- key line
                    fg=zynthian_gui_config.color_tx,
                    activeforeground=zynthian_gui_config.color_tx
                )
            else:
                off_bg = zynthian_gui_config.color_panel_bg
                btn.config(
                    bg=off_bg,
                    activebackground=off_bg,  # optional, keeps hover same as normal
                    fg=zynthian_gui_config.color_tx,
                    activeforeground=zynthian_gui_config.color_tx
                )

    def update_canvas_display(self):
        """Update display to show the selected scale"""
        self.update_all_markers()
        logging.info(f"Displaying Scale {self.selected_scale + 1}")

    def set_tuning(self, scale, note, value):
        """Set the tuning value for a note on a scale and update the UI if visible."""
        if scale in self.tunings and note in self.tunings[scale]:
            self.tunings[scale][note] = round(float(value), 2)
            if scale == self.selected_scale:
                idx = self.notes.index(note)
                cents = self.tunings[scale][note]
                val = (50 - cents) / 100
                self.update_slider_marker(self.note_canvases[idx], val)
                self.cents_labels[idx].config(text=f"{cents:.2f}")
                logging.info(f"Set tuning {note} on scale {scale} to {cents:.2f} cents")

    def update_slider_marker(self, canvas, value):
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        marker_y = value * height
        # Delete old marker and redraw
        canvas.delete("marker")
        canvas.create_line(0, marker_y, width, marker_y, fill='red', width=2, tags="marker")

    def on_slider_press(self, event, idx):
        self.slider_press_event = event

    def on_slider_release(self, event):
        self.slider_press_event = None

    def on_slider_motion(self, event, idx):
        if self.slider_press_event:
            canvas = self.note_canvases[idx]
            height = canvas.winfo_height()
            value = max(0, min(1, event.y / height))
            cents = 50 - (value * 100)  # Top = +50, bottom = -50
            note = self.notes[idx]
            self.tunings[self.selected_scale][note] = round(cents, 2)
            self.update_slider_marker(canvas, value)
            self.cents_labels[idx].config(text=f"{cents:.2f}")
            logging.info(f"Tuning {note} on scale {self.selected_scale} to {cents:.2f} cents")

    def show(self):
        super().show()
        self.set_select_path()

    def hide(self):
        super().hide()

    def set_select_path(self):
        self.select_path.set("Microtuning")

    def back_action(self):
        self.zyngui.show_screen("main_menu")

# ------------------------------------------------------------------------------