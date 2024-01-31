import requests


class LEDConnectorProviderRole():

    def _controlLedOperation(self, schalter):
        # Handle the control LED operation
        if schalter.lower() == "on":
            print("Turning on the LED...")
            # Simulate making an API request to turn on the LED
            self._makeApiRequest("win&T=1")
        elif schalter.lower() == "off":
            print("Turning off the LED...")
            # Simulate making an API request to turn off the LED
            self._makeApiRequest("win&T=0")
        else:
            print(f"Unknown argument: {schalter}")

    def _Primary_Colorchange(self, Primary_color):
        # Handle the control LED operation HEX/DEC
        print("Changing primary color...")
            # Simulate making an API request to turn on the LED
        self._makeApiRequest("win&CL="+ Primary_color)

    def _Secondary_Colorchange(self, Secondary_color):
        # Handle the control LED operation HEX/DEC
        print("Changing secondary color...")
            # Simulate making an API request to turn on the LED
        self._makeApiRequest("win&C2="+ Secondary_color)

    def _Third_Colorchange(self, Third_color):
        # Handle the control LED operation HEX/DEC
        print("Changing third color...")
            # Simulate making an API request to turn on the LED
        self._makeApiRequest("win&C3="+ Third_color)

    def _BrightnessChange(self, brightness):
        # Handle the control LED operation 0-255
        print("Changing the brigtness...")
        self._makeApiRequest("win&SB="+ str(brightness))

    def _EffectSpeed(self, speed):
        # Handle the control LED operation 0-255
        print("Changing the speed...")
        self._makeApiRequest("win&SX="+ str(speed))

    def _EffectIntensity(self, intensity):
        # Handle the control LED operation 0-255
        print("Changing the intensity...")
        self._makeApiRequest("win&IX="+ str(intensity))

    def _LED_Effect_Index(self, Effect_Index):
        # Handle the control LED operation 0-101
        print("Changing the effect...")
        self._makeApiRequest("win&FX="+ str(Effect_Index))

    def _LED_Palette_Index(self, Palette_Index):
        # Handle the control LED operation 0-46
        print("Changing the Palette...")
        self._makeApiRequest("win&FP="+ str(Palette_Index))

        
    
            


    def _makeApiRequest(self, endpoint):
        # Simulate making an API request to control the LED
        full_url = f"http://10.249.117.79/{endpoint}"
        response = requests.post(full_url)
        if response.status_code == 200:
            print(f"API request successful: {endpoint}")
        else:
            print(f"API request failed with status code {response.status_code}: {endpoint}")


    

        

#LEDConnectorProviderRole()._controlLedOperation(schalter = "on")
#LEDConnectorProviderRole()._LED_Effect_Index(Effect_Index=9)
#LEDConnectorProviderRole()._Primary_Colorchange(Primary_color="#FFFF00")
#LEDConnectorProviderRole()._Secondary_Colorchange(Secondary_color="#F72E03")
#LEDConnectorProviderRole()._Third_Colorchange(Third_color="#888800")
#LEDConnectorProviderRole()._BrightnessChange(brightness=200)
#LEDConnectorProviderRole()._EffectSpeed(speed=200)
#LEDConnectorProviderRole()._EffectIntensity(intensity=150)
#LEDConnectorProviderRole()._LED_Palette_Index(Palette_Index=40)