"""
LaudaT2200.py - A Tango DS for controlling the Lauda T2200 chiller.

Author: Igor Beinik
Date: 2021-08-12
"""

import tango
from tango import DevState, AttrWriteType, DispLevel, DevBoolean, DevString
from tango.server import Device, device_property, command, attribute
import serial
import threading
import time

class LaudaT2200(Device):

    # ----- Device Properties -----
    serialport = device_property(dtype=str, default_value='/dev/ttyS2')
    baudrate = device_property(dtype=int, default_value=9600)
    timeout = device_property(dtype=int, default_value=1)

    def init_device(self):
        Device.init_device(self)
        self.set_state(DevState.INIT)

        self.serial_port = None
        self.serial_lock = threading.Lock()
        self._bath_temp = 0.0
        self._temp_setp = 21.0  # Initialize setpoint to 0
        self._temp_setp_changed = False
        self._chiller_status = ""
        self._is_on = False
        self._is_on_toggle = False
        self._pressure = 0.0

        print(f"Connecting to chiller at {self.serialport} with baudrate {self.baudrate} and timeout {self.timeout}...")

        try:
            # Initialize serial connection using device properties
            self.serial_port = serial.Serial(
                port=self.serialport,
                baudrate=self.baudrate,
                timeout=self.timeout
            )

            # Open the port
            if not self.serial_port.isOpen():
                self.serial_port.open()
            
            command = "STATUS\r\n"
            self.serial_port.write(command.encode())
            response = self.serial_port.readline().decode().strip()
            self.info_stream(f'init_device: status is: {response}')

            if int(response) == 0:
                self.set_state(DevState.ON)
            elif int(response) == -1:
                self.set_state(DevState.FAULT)
                self.error_stream("Chiller is in alarm state")

            # Start the communication thread
            self.comm_thread = threading.Thread(target=self._communication_loop)
            self.comm_thread.daemon = True
            self.comm_thread.start()
        except Exception as e:
            print('init_device: ', e)
            self.error_stream(f"init_device: {e}")
            self.set_state(DevState.FAULT)

    # ----- Attributes -----

    bath_temp = attribute(
        label="Bath Temp.",
        dtype=tango.DevFloat,
        access=AttrWriteType.READ,
        display_level=DispLevel.OPERATOR,
        unit="C",
        format="%5.2f",
        doc="Bath temperature of the chiller",
    )

    temp_setp = attribute(
        label="Temp. Setpoint",
        dtype=tango.DevFloat,
        access=AttrWriteType.READ_WRITE,
        display_level=DispLevel.OPERATOR,
        unit="C",
        format="%5.2f",
        doc="Target temperature setpoint for the chiller",
    )

    chiller_status = attribute(
        label="Chiller Status",
        dtype=str,
        access=AttrWriteType.READ,
        display_level=DispLevel.OPERATOR,
        doc="Current status of the chiller (read manual for codes)"
    )

    is_on = attribute(
        label="Is On",
        dtype=DevBoolean,
        access=AttrWriteType.READ_WRITE,
        display_level=DispLevel.OPERATOR,
        doc="Indicates if the chiller is on (True) or off (False)"
    )

    pressure = attribute(
        label="Pressure",
        dtype=tango.DevFloat,
        access=AttrWriteType.READ,
        display_level=DispLevel.OPERATOR,
        unit="bar",
        format="%5.2f",
        doc="Current pressure of the chiller",
    )

    # ----- Serial Communication Thread -----
    def _communication_loop(self):
        while True:
            with self.serial_lock:
                self._write_is_on()
                self._write_setp()
            
            with self.serial_lock:
                self._read_bath_temp()
                self._read_pressure()
                self._read_setp()
                self._read_chiller_status()
            
            with self.serial_lock:   
                self._read_is_on()

            time.sleep(1)


    # ----- Data Reading Functions -----
    def _read_bath_temp(self):
        command = "IN_PV_00\r\n"
        self.serial_port.write(command.encode())
        response = self.serial_port.readline().decode().strip()
        try:
            self._bath_temp = float(response)
        except ValueError:
            self.error_stream(f"Invalid temperature response: {response}")

    def _read_chiller_status(self):
        command = "STATUS\r\n"
        self.serial_port.write(command.encode())
        response = self.serial_port.readline().decode().strip()

        if int(float(response)) == 0:
            pass
        elif int(float(response)) == -1:
            self.set_state(DevState.FAULT)
            self.error_stream("Chiller is in alarm state")

        command = "STAT\r\n"
        self.serial_port.write(command.encode())
        response = self.serial_port.readline().decode().strip()
        self._chiller_status = response

    def _read_pressure(self):
        command = "IN_PV_02\r\n"  
        self.serial_port.write(command.encode())
        response = self.serial_port.readline().decode().strip()
        try:
            self._pressure = float(response)
        except ValueError:
            self.error_stream(f"Invalid pressure response: {response}")

    def _read_is_on(self):
        command = "IN_MODE_02\r\n"  
        self.serial_port.write(command.encode())
        response = self.serial_port.readline().decode().strip()
        try:
            r = int(float(response))
            if r == 0:
                self._is_on = True
                self.set_state(tango.DevState.RUNNING)
            elif r == 1:
                self._is_on = False
        except ValueError:
            self.error_stream(f"Invalid is_on response: {response}")

    def _write_is_on(self):
        if self._is_on_toggle:
            command = "START\r\n" if self._is_on else "STOP\r\n"  
            self.serial_port.write(command.encode())
            response = self.serial_port.readline().decode().strip()
            self.info_stream(f'On/Off state toggled, response: {response}')
            time.sleep(1)
            if self._is_on:
                self.set_state(tango.DevState.RUNNING)
            else:
                self.set_state(tango.DevState.ON)
            self.push_change_event("is_on", self._is_on)
            self._is_on_toggle = False

    def _read_setp(self):
        command = "IN_SP_00\r\n"  
        self.serial_port.write(command.encode())
        response = self.serial_port.readline().decode().strip()
        try:
            self._temp_setp = float(response)
        except ValueError:
            self.error_stream(f"Invalid setpoint read response: {response}")

    def _write_setp(self):
        if self._temp_setp_changed:
            command = f"OUT_SP_00_{self._temp_setp}\r\n"  
            self.serial_port.write(command.encode())
            response = self.serial_port.readline().decode().strip()
            self.info_stream(f'Setpoint changed to {self._temp_setp}, response: {response}')
            self._temp_setp_changed = False
            

    # ----- Attribute Read -----
    def read_bath_temp(self):
        return self._bath_temp

    def read_temp_setp(self):
        return self._temp_setp

    def read_chiller_status(self):
        return self._chiller_status

    def read_is_on(self):
        return self._is_on

    def read_pressure(self):
        return self._pressure
    
    # ---Writer Methods---
    def write_temp_setp(self, value):
        self._temp_setp = value
        self._temp_setp_changed = True

    def write_is_on(self, value):
        self._is_on_toggle = True
        self._is_on = value

if __name__ == "__main__":
    LaudaT2200.run_server()

