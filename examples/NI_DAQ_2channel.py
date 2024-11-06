import nidaqmx
from nidaqmx.constants import (
    Edge, Level, TriggerType
)
import time

# # Create the untriggered counting task
# untriggered_task = nidaqmx.Task()
# untriggered_task.ci_channels.add_ci_count_edges_chan(
#     counter="Dev1/ctr0",  # Channel for untriggered counting
#     name_to_assign_to_channel="Untriggered Count",
#     edge=Edge.RISING  # Assuming rising edge
# )
# untriggered_task.ci_channels.ci_count_edges_term = "/Dev1/PFI4"  # Set terminal for untriggered channel

triggered_task = nidaqmx.Task()
triggered_task.ci_channels.add_ci_count_edges_chan(
    counter="Dev1/ctr0",  # Update with the correct counter channel (e.g., "Dev1/ctr0")
    name_to_assign_to_channel="",
    edge=Edge.RISING  # Assuming rising edge, adjust if falling edge is needed
)
# triggered_task.ci_channels.ci_count_edges_term = "/Dev1/PFI4"
# Configure the digital level pause trigger
triggered_task.triggers.pause_trigger.trig_type = TriggerType.DIGITAL_LEVEL  # Set the trigger type
triggered_task.triggers.pause_trigger.dig_lvl_src = "/Dev1/PFI3"  # Update with the correct PFI line for the gate
triggered_task.triggers.pause_trigger.dig_lvl_when = Level.HIGH  # Assuming LOW level, adjust to HIGH if necessary



# Start the tasks
# untriggered_task.start()
triggered_task.start()

# Allow time for counting
time.sleep(1)  # Wait for 1 second for counting to occur

triggered_count = triggered_task.read()  # Read the count value from triggered task
print("Triggered Count:", triggered_count)

# untriggered_count = untriggered_task.read()  # Read the count value from untriggered task
# print("Untriggered Count:", untriggered_count)


# Stop the tasks when done
# untriggered_task.stop()
triggered_task.stop()

# Clean up
# untriggered_task.close()
triggered_task.close()
