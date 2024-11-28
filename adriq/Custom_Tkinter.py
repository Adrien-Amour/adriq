import tkinter as tk
from tkinter import ttk
from decimal import Decimal

class CustomIntSpinbox(ttk.Spinbox):
    def __init__(self, master=None, from_=0, to=None, initial_value=0, **kwargs):
        self.var = tk.IntVar()
        if initial_value is None:
            initial_value = 0  # Set a default value if initial_value is None
        super().__init__(master, from_=from_, to=to if to is not None else float('inf'), **kwargs)

        # Set the initial value
        self.var.set(str(initial_value))

        # Bind events
        self.bind("<Up>", self.increment_digit)
        self.bind("<Down>", self.decrement_digit)
        self.bind("<Shift-Up>", self.increment_digit_right)
        self.bind("<Shift-Down>", self.decrement_digit_right)
        self.bind("<Return>", self.send_value)
        self.bind("<FocusOut>", self.send_value)  # Send value on focus out
        self.bind("<Button-1>", self.clear_selection)  # Clear selection on mouse click

        self.callback = None
        self.min_value = from_
        self.max_value = to

        # Override the default spinbox button commands
        self.configure(command=self.send_value)

        # Send the initial value to the callback if set
        self.send_value()

    def increment_digit(self, event):
        self._adjust_digit(1, left=True)
        self.send_value()  # Send value after increment
        return "break"  # Prevent default behavior

    def decrement_digit(self, event):
        self._adjust_digit(-1, left=True)
        self.send_value()  # Send value after decrement
        return "break"  # Prevent default behavior

    def increment_digit_right(self, event):
        self._adjust_digit(1, left=False)
        self.send_value()  # Send value after increment
        return "break"  # Prevent default behavior

    def decrement_digit_right(self, event):
        self._adjust_digit(-1, left=False)
        self.send_value()  # Send value after decrement
        return "break"  # Prevent default behavior

    def _adjust_digit(self, adjustment, left):
        current_value = self.get()
        cursor_position = self.index(tk.INSERT)

        try:
            value = float(current_value)
        except ValueError:
            return  # Ignore if not a valid float

        # Determine the factor for adjustment based on cursor position
        if '.' in current_value:
            decimal_pos = current_value.index('.')
            if left:
                if cursor_position > decimal_pos:
                    factor = 10 ** (decimal_pos - cursor_position + 1)
                else:
                    factor = 10 ** (decimal_pos - cursor_position)
            else:
                if cursor_position > decimal_pos:
                    factor = 10 ** (decimal_pos - cursor_position)
                else:
                    factor = 10 ** (decimal_pos - cursor_position - 1)
        else:
            if left:
                factor = 10 ** (len(current_value) - cursor_position)
            else:
                factor = 10 ** (len(current_value) - cursor_position - 1)
        if factor >= 1:
            new_value = value + adjustment * factor
        else:
            new_value = value
        self.set(int(new_value))

    def send_value(self, event=None):
        try:
            value = float(self.get())
            rounded_value = int(round(value))
            if value != rounded_value:
                self.set(rounded_value)
                value = rounded_value
            if value < self.min_value:
                self.set(self.min_value)
                value = self.min_value
            elif self.max_value is not None and value > self.max_value:
                self.set(self.max_value)
                value = self.max_value
        except ValueError:
            self.set(self.min_value)
            value = self.min_value

        if self.callback:
            self.callback(value)

    def set_callback(self, callback):
        self.callback = callback

    def clear_selection(self, event):
        self.selection_clear()


class CustomSpinbox(ttk.Spinbox):
    def __init__(self, master=None, from_=0.0, to=100.0, initial_value=0.0, **kwargs):
        self.var = tk.StringVar()
        super().__init__(master, from_=from_, to=to, textvariable=self.var, **kwargs)

        # Set the initial value
        self.var.set(str(initial_value))

        # Bind events
        self.bind("<Up>", self.increment_digit)
        self.bind("<Down>", self.decrement_digit)
        self.bind("<Shift-Up>", self.increment_digit_right)
        self.bind("<Shift-Down>", self.decrement_digit_right)
        self.bind("<Return>", self.send_value)
        self.bind("<FocusOut>", self.send_value)  # Send value on focus out
        self.bind("<Button-1>", self.clear_selection)  # Clear selection on mouse click

        self.callback = None
        self.min_value = Decimal(str(from_))
        self.max_value = Decimal(str(to))

        # Override the default spinbox button commands
        self.configure(command=self.send_value)

        # Send the initial value to the callback if set
        self.send_value()

    def increment_digit(self, event):
        self._adjust_digit(1, left=True)
        self.send_value()  # Send value after increment
        return "break"  # Prevent default behavior

    def decrement_digit(self, event):
        self._adjust_digit(-1, left=True)
        self.send_value()  # Send value after decrement
        return "break"  # Prevent default behavior

    def increment_digit_right(self, event):
        self._adjust_digit(1, left=False)
        self.send_value()  # Send value after increment
        return "break"  # Prevent default behavior

    def decrement_digit_right(self, event):
        self._adjust_digit(-1, left=False)
        self.send_value()  # Send value after decrement
        return "break"  # Prevent default behavior

    def _adjust_digit(self, adjustment, left):
        current_value = self.var.get()
        cursor_position = self.index(tk.INSERT)

        try:
            value = Decimal(current_value)
        except ValueError:
            return  # Ignore if not a valid decimal

        # Determine the factor for adjustment based on cursor position
        if '.' in current_value:
            decimal_pos = current_value.index('.')
            if left:
                if cursor_position > decimal_pos:
                    factor = Decimal('10') ** (decimal_pos - cursor_position + 1)
                else:
                    factor = Decimal('10') ** (decimal_pos - cursor_position)
            else:
                if cursor_position > decimal_pos:
                    factor = Decimal('10') ** (decimal_pos - cursor_position)
                else:
                    factor = Decimal('10') ** (decimal_pos - cursor_position - 1)
        else:
            if left:
                factor = Decimal('10') ** (len(current_value) - cursor_position)
            else:
                factor = Decimal('10') ** (len(current_value) - cursor_position - 1)

        new_value = value + Decimal(adjustment) * factor
        self.var.set(format(new_value, 'f'))

        # Adjust cursor position
        new_cursor_position = cursor_position
        if new_value < 0 and value >= 0:
            new_cursor_position += 1
        elif new_value >= 0 and value < 0:
            new_cursor_position -= 1

        self.icursor(new_cursor_position)

    def send_value(self, event=None):
        try:
            value = Decimal(self.var.get())
            if value < self.min_value:
                self.var.set(self.min_value)
                value = self.min_value
            elif value > self.max_value:
                self.var.set(self.max_value)
                value = self.max_value
        except ValueError:
            self.var.set(self.min_value)
            value = self.min_value

        if self.callback:
            self.callback(float(value))

    def set_callback(self, callback):
        self.callback = callback

    def clear_selection(self, event):
        self.selection_clear()

class CustomBinarySpinbox(ttk.Spinbox):
    def __init__(self, master=None, from_=0, to=65535, initial_value=0, **kwargs):
        self.var = tk.StringVar()
        if initial_value is None:
            initial_value = 0  # Set a default value if initial_value is None
        super().__init__(master, from_=from_, to=to, textvariable=self.var, **kwargs)

        # Set the initial value
        self.var.set(format(initial_value, '016b'))

        # Bind events
        self.bind("<Up>", self.increment_digit)
        self.bind("<Down>", self.decrement_digit)
        self.bind("<Shift-Up>", self.increment_digit_right)
        self.bind("<Shift-Down>", self.decrement_digit_right)
        self.bind("<Return>", self.send_value)
        self.bind("<FocusOut>", self.send_value)  # Send value on focus out
        self.bind("<Button-1>", self.clear_selection)  # Clear selection on mouse click

        self.callback = None
        self.min_value = from_
        self.max_value = to

        # Override the default spinbox button commands
        self.configure(command=self.send_value)

        # Send the initial value to the callback if set
        self.send_value()

    def increment_digit(self, event):
        if self.index(tk.INSERT) < 16:  # Check if cursor is within the valid range
            self._adjust_digit(1, left=True)
            self.send_value()  # Send value after increment
        return "break"  # Prevent default behavior

    def decrement_digit(self, event):
        if self.index(tk.INSERT) < 16:  # Check if cursor is within the valid range
            self._adjust_digit(-1, left=True)
            self.send_value()  # Send value after decrement
        return "break"  # Prevent default behavior

    def increment_digit_right(self, event):
        if self.index(tk.INSERT) < 16:  # Check if cursor is within the valid range
            self._adjust_digit(1, left=False)
            self.send_value()  # Send value after increment
        return "break"  # Prevent default behavior

    def decrement_digit_right(self, event):
        if self.index(tk.INSERT) < 16:  # Check if cursor is within the valid range
            self._adjust_digit(-1, left=False)
            self.send_value()  # Send value after decrement
        return "break"  # Prevent default behavior

    def _adjust_digit(self, adjustment, left):
        current_value = self.var.get()
        cursor_position = self.index(tk.INSERT)

        try:
            value = int(current_value, 2)
        except ValueError:
            return  # Ignore if not a valid binary number

        # Determine the factor for adjustment based on cursor position
        bit_position = 15 - cursor_position
        if bit_position < 0 or bit_position > 15:
            return  # Ignore if bit position is out of range

        if left:
            new_value = value + (adjustment << bit_position)
        else:
            new_value = value + (adjustment << (bit_position - 1))

        new_value = max(self.min_value, min(new_value, self.max_value))
        self.var.set(format(new_value, '016b'))

    def send_value(self, event=None):
        try:
            value = int(self.var.get(), 2)
            if value < self.min_value:
                self.var.set(format(self.min_value, '016b'))
                value = self.min_value
            elif self.max_value is not None and value > self.max_value:
                self.var.set(format(self.max_value, '016b'))
                value = self.max_value
        except ValueError:
            self.var.set(format(self.min_value, '016b'))
            value = self.min_value

        if self.callback:
            self.callback(value)

    def set_callback(self, callback):
        self.callback = callback

    def clear_selection(self, event):
        self.selection_clear()
    def __init__(self, master=None, from_=0, to=65535, initial_value=0, **kwargs):
        self.var = tk.StringVar()
        if initial_value is None:
            initial_value = 0  # Set a default value if initial_value is None
        super().__init__(master, from_=from_, to=to, textvariable=self.var, **kwargs)

        # Set the initial value
        self.var.set(format(initial_value, '016b'))

        # Bind events
        self.bind("<Up>", self.increment_digit)
        self.bind("<Down>", self.decrement_digit)
        self.bind("<Shift-Up>", self.increment_digit_right)
        self.bind("<Shift-Down>", self.decrement_digit_right)
        self.bind("<Return>", self.send_value)
        self.bind("<FocusOut>", self.send_value)  # Send value on focus out
        self.bind("<Button-1>", self.clear_selection)  # Clear selection on mouse click

        self.callback = None
        self.min_value = from_
        self.max_value = to

        # Override the default spinbox button commands
        self.configure(command=self.send_value)

        # Send the initial value to the callback if set
        self.send_value()

    def increment_digit(self, event):
        if self.index(tk.INSERT) < 16:  # Check if cursor is within the valid range
            self._adjust_digit(1, left=True)
            self.send_value()  # Send value after increment
        return "break"  # Prevent default behavior

    def decrement_digit(self, event):
        if self.index(tk.INSERT) < 16:  # Check if cursor is within the valid range
            self._adjust_digit(-1, left=True)
            self.send_value()  # Send value after decrement
        return "break"  # Prevent default behavior

    def increment_digit_right(self, event):
        if self.index(tk.INSERT) < 16:  # Check if cursor is within the valid range
            self._adjust_digit(1, left=False)
            self.send_value()  # Send value after increment
        return "break"  # Prevent default behavior

    def decrement_digit_right(self, event):
        if self.index(tk.INSERT) < 16:  # Check if cursor is within the valid range
            self._adjust_digit(-1, left=False)
            self.send_value()  # Send value after decrement
        return "break"  # Prevent default behavior

    def _adjust_digit(self, adjustment, left):
        current_value = self.var.get()
        cursor_position = self.index(tk.INSERT)

        try:
            value = int(current_value, 2)
        except ValueError:
            return  # Ignore if not a valid binary number

        # Determine the factor for adjustment based on cursor position
        bit_position = 15 - cursor_position
        if bit_position < 0 or bit_position > 15:
            return  # Ignore if bit position is out of range

        if left:
            new_value = value + (adjustment << bit_position)
        else:
            new_value = value + (adjustment << (bit_position - 1))

        new_value = max(self.min_value, min(new_value, self.max_value))
        self.var.set(format(new_value, '016b'))

    def send_value(self, event=None):
        try:
            value = int(self.var.get(), 2)
            if value < self.min_value:
                self.var.set(format(self.min_value, '016b'))
                value = self.min_value
            elif self.max_value is not None and value > self.max_value:
                self.var.set(format(self.max_value, '016b'))
                value = self.max_value
        except ValueError:
            self.var.set(format(self.min_value, '016b'))
            value = self.min_value

        if self.callback:
            self.callback(value)

    def set_callback(self, callback):
        self.callback = callback

    def clear_selection(self, event):
        self.selection_clear()
    def __init__(self, master=None, from_=0, to=65535, initial_value=0, **kwargs):
        self.var = tk.StringVar()
        if initial_value is None:
            initial_value = 0  # Set a default value if initial_value is None
        super().__init__(master, from_=from_, to=to, textvariable=self.var, **kwargs)

        # Set the initial value
        self.var.set(format(initial_value))

        # Bind events
        self.bind("<Up>", self.increment_digit)
        self.bind("<Down>", self.decrement_digit)
        self.bind("<Shift-Up>", self.increment_digit_right)
        self.bind("<Shift-Down>", self.decrement_digit_right)
        self.bind("<Return>", self.send_value)
        self.bind("<FocusOut>", self.send_value)  # Send value on focus out
        self.bind("<Button-1>", self.clear_selection)  # Clear selection on mouse click

        self.callback = None
        self.min_value = from_
        self.max_value = to

        # Override the default spinbox button commands
        self.configure(command=self.send_value)

        # Send the initial value to the callback if set
        self.send_value()

    def increment_digit(self, event):
        if self.index(tk.INSERT) < 15:  # Check if cursor is within the valid range
            self._adjust_digit(1, left=True)
            self.send_value()  # Send value after increment
        return "break"  # Prevent default behavior

    def decrement_digit(self, event):
        if self.index(tk.INSERT) < 15:  # Check if cursor is within the valid range
            self._adjust_digit(-1, left=True)
            self.send_value()  # Send value after decrement
        return "break"  # Prevent default behavior

    def increment_digit_right(self, event):
        if self.index(tk.INSERT) < 15:  # Check if cursor is within the valid range
            self._adjust_digit(1, left=False)
            self.send_value()  # Send value after increment
        return "break"  # Prevent default behavior

    def decrement_digit_right(self, event):
        if self.index(tk.INSERT) < 15:  # Check if cursor is within the valid range
            self._adjust_digit(-1, left=False)
            self.send_value()  # Send value after decrement
        return "break"  # Prevent default behavior

    def _adjust_digit(self, adjustment, left):
        current_value = self.var.get()
        cursor_position = self.index(tk.INSERT)

        try:
            value = int(current_value, 2)
        except ValueError:
            return  # Ignore if not a valid binary number

        # Determine the factor for adjustment based on cursor position
        bit_position = 15 - cursor_position
        if left:
            new_value = value + (adjustment << bit_position)
        else:
            new_value = value + (adjustment << (bit_position - 1))

        new_value = max(self.min_value, min(new_value, self.max_value))
        self.var.set(format(new_value, '016b'))

    def send_value(self, event=None):
        try:
            value = int(self.var.get(), 2)
            if value < self.min_value:
                self.var.set(format(self.min_value, '016b'))
                value = self.min_value
            elif self.max_value is not None and value > self.max_value:
                self.var.set(format(self.max_value, '016b'))
                value = self.max_value
        except ValueError:
            self.var.set(format(self.min_value, '016b'))
            value = self.min_value

        if self.callback:
            self.callback(value)

    def set_callback(self, callback):
        self.callback = callback

    def clear_selection(self, event):
        self.selection_clear()
    def __init__(self, master=None, from_=0, to=65535, initial_value=0, **kwargs):
        self.var = tk.StringVar()
        if initial_value is None:
            initial_value = 0  # Set a default value if initial_value is None
        super().__init__(master, from_=from_, to=to, textvariable=self.var, **kwargs)

        # Set the initial value
        self.var.set(format(initial_value))

        # Bind events
        self.bind("<Up>", self.increment_digit)
        self.bind("<Down>", self.decrement_digit)
        self.bind("<Shift-Up>", self.increment_digit_right)
        self.bind("<Shift-Down>", self.decrement_digit_right)
        self.bind("<Return>", self.send_value)
        self.bind("<FocusOut>", self.send_value)  # Send value on focus out
        self.bind("<Button-1>", self.clear_selection)  # Clear selection on mouse click

        self.callback = None
        self.min_value = from_
        self.max_value = to

        # Override the default spinbox button commands
        self.configure(command=self.send_value)

        # Send the initial value to the callback if set
        self.send_value()

    def increment_digit(self, event):
        self._adjust_digit(1, left=True)
        self.send_value()  # Send value after increment
        return "break"  # Prevent default behavior

    def decrement_digit(self, event):
        self._adjust_digit(-1, left=True)
        self.send_value()  # Send value after decrement
        return "break"  # Prevent default behavior

    def increment_digit_right(self, event):
        self._adjust_digit(1, left=False)
        self.send_value()  # Send value after increment
        return "break"  # Prevent default behavior

    def decrement_digit_right(self, event):
        self._adjust_digit(-1, left=False)
        self.send_value()  # Send value after decrement
        return "break"  # Prevent default behavior

    def _adjust_digit(self, adjustment, left):
        current_value = self.var.get()
        cursor_position = self.index(tk.INSERT)

        try:
            value = int(current_value, 2)
        except ValueError:
            return  # Ignore if not a valid binary number

        # Determine the factor for adjustment based on cursor position
        bit_position = 15 - cursor_position
        if left:
            new_value = value + (adjustment << bit_position)
        else:
            new_value = value + (adjustment << (bit_position - 1))

        new_value = max(self.min_value, min(new_value, self.max_value))
        self.var.set(format(new_value, '016b'))

    def send_value(self, event=None):
        try:
            value = int(self.var.get(), 2)
            if value < self.min_value:
                self.var.set(format(self.min_value, '016b'))
                value = self.min_value
            elif self.max_value is not None and value > self.max_value:
                self.var.set(format(self.max_value, '016b'))
                value = self.max_value
        except ValueError:
            self.var.set(format(self.min_value, '016b'))
            value = self.min_value

        if self.callback:
            self.callback(value)

    def set_callback(self, callback):
        self.callback = callback

    def clear_selection(self, event):
        self.selection_clear()