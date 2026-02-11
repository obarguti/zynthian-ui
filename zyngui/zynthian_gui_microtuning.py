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
        self.note_buttons = []  # Store note buttons for the keyboard

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
        white_width = 4
        white_height = 9
        black_width = 4
        black_height = 8

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
        total_w = 7 * white_px_w + 6 * key_gap
        total_h = white_px_h + black_px_h
        self.keyboard_frame = tkinter.Frame(self.canvas_frame, bg=zynthian_gui_config.color_panel_bg,
                                            width=total_w, height=total_h)
        self.keyboard_frame.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)
        self.keyboard_frame.pack_propagate(False)

        # Precompute x positions of white keys
        white_x = [i * (white_px_w + key_gap) for i in range(7)]

        # White keys
        white_y = black_px_h
        for i, note in enumerate(white_notes):
            btn = tkinter.Button(
                self.keyboard_frame,
                text=note,
                font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size),
                bg="white",
                fg="black",
                activebackground="white",
                bd=1,
                highlightthickness=0,
                relief=tkinter.RAISED,
                command=lambda n=note: self.note_pressed(n)
            )
            btn.place(x=white_x[i], y=white_y, width=white_px_w, height=white_px_h)
            self.note_buttons.append(btn)

        # Black keys
        black_y = 0
        for left_i, note in black_map:
            boundary_center = white_x[left_i] + white_px_w + (key_gap / 2.0)
            bx = int(round(boundary_center - (black_px_w / 2.0)))

            btn = tkinter.Button(
                self.keyboard_frame,
                text=note,
                font=(zynthian_gui_config.font_family, zynthian_gui_config.font_size),
                bg=zynthian_gui_config.color_panel_bd,
                fg=zynthian_gui_config.color_tx,
                activebackground=zynthian_gui_config.color_panel_bd,
                bd=0,
                highlightthickness=0,
                relief=tkinter.FLAT,
                command=lambda n=note: self.note_pressed(n)
            )
            btn.place(x=bx, y=black_y, width=black_px_w, height=black_px_h)
            self.note_buttons.append(btn)

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
        # Could update note button states or other visual feedback here
        logging.info(f"Displaying Scale {self.selected_scale + 1}")

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