# example main modules

The examples directory provides example `main.py` modules for command station and local block detection and an example JMRI Jython script that imports MQTT RailCom information into JMRI tables.

These modules contain installation specific code and may need to be edited, for example, if using a layout conrol bus as an alternative to MQTT or to reflect other local configuration requirements.

The 'main.py' modules dictate the 'personality' of the run-time application and specify
 which of the package modules are invoked at run-time. E.g whether command station, or 
 block detection modules are loaded.
