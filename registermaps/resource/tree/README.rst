================
Text Tree Output
================

An extremely basic text output, primarily useful for debugging.
Example output is::

	component VMESPACE (size=256)
		The VMESPACE peripheral holds registers to the VMEbus. An array of 256 16bit VME registers will
		be implemented per described in the V280 manual.
		This is visible only to the internal bus.
		(0) MFR
			Highland ID
		(1) MODEL
			V280 Model ID
		(2) MODREV
			Hardware Revision
		(3) SERIAL
			Unit serial number
		(4) FIRWARE
			Programmed firmware
		(5) FREV
			Firmware revision
		(6) MCOUNT
			1KHz real-time counter
		(7) DASH
			Unit dash number
		(8) CALID
			Calibration table status
		(9) YCAL
			Calibration date: year
		(10) DCAL
			Calibration date: month/day
			Field DAY (writeOnly=None,format=bits,size=8,offset=0,readOnly=None)
				Day (1-31)
			Field MONTH (writeOnly=None,format=bits,size=8,offset=8,readOnly=None)
				Month (1-12)
		(12) ULED
			User LED control
		(16) MACRO
			Macro register
		RegisterArray MPARAM (writeOnly=False,count=4,offset=17,readOnly=False,size=4,framesize=1)
			Macro parameter registers
			(0) PARAMn
		RegisterArray STATUS (writeOnly=False,count=3,offset=24,readOnly=False,size=3,framesize=1)
			Current status of inputs
			(0) STATUSn
		RegisterArray RISE (writeOnly=False,count=3,offset=28,readOnly=False,size=3,framesize=1)
			Rise debounce time
			(0) RISEn
		RegisterArray FALL (writeOnly=False,count=3,offset=32,readOnly=False,size=3,framesize=1)
			Fall debouce time
			(0) FALLn
		RegisterArray BISTERROR (writeOnly=False,count=3,offset=36,readOnly=False,size=3,framesize=1)
			Error registers for BIST
			(0) BISTERRn
		RegisterArray BUFFER (writeOnly=False,count=128,offset=128,readOnly=False,size=128,framesize=1)
			Buffer registers
			(0) BUFFn
