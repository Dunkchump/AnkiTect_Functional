import flet as ft
import inspect

# Dropdown params
sig = inspect.signature(ft.Dropdown.__init__)
params = [p for p in sig.parameters.keys()]
on_params = [p for p in params if 'on_' in p or 'change' in p or 'select' in p]
print("Dropdown all on_* params:", on_params)

# Check if on_change exists
print("Has on_change attr:", hasattr(ft.Dropdown, 'on_change'))
print("Has on_select attr:", hasattr(ft.Dropdown, 'on_select'))

# Try to see Dropdown source
try:
    src = inspect.getfile(ft.Dropdown)
    print("Dropdown source file:", src)
except:
    pass

# Check Switch
sig2 = inspect.signature(ft.Switch.__init__)
sw_on = [p for p in sig2.parameters.keys() if 'on_' in p or 'change' in p]
print("Switch on_* params:", sw_on)
