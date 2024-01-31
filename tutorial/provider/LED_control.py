import requests


class LEDConnectorProviderRole():

    def _controlLedOperation(self, argument):
        # Handle the control LED operation
        if argument.lower() == "on":
            print("Turning on the LED...")
            # Simulate making an API request to turn on the LED
            self._makeApiRequest("win&T=1")
        elif argument.lower() == "off":
            print("Turning off the LED...")
            # Simulate making an API request to turn off the LED
            self._makeApiRequest("win&T=0")
        else:
            print(f"Unknown argument: {argument}")

    def _Colorchange(self, argument):
        # Handle the control LED operation
        if argument.lower() == "red":
            print("Changing color to red...")
            # Simulate making an API request to turn on the LED
            self._makeApiRequest("red&T=1")
        elif argument.lower() == "green":
            print("Changing color to green...")
            # Simulate making an API request to turn off the LED
            self._makeApiRequest("green&T=1")
        elif argument.lower() == "blue":
            print("Changing color to blue...")
            # Simulate making an API request to turn off the LED
            self._makeApiRequest("blue&T=1")
        else:
            print(f"Unknown argument: {argument}")


    def _makeApiRequest(self, endpoint):
        # Simulate making an API request to control the LED
        full_url = f"http://10.249.117.79/{endpoint}"
        response = requests.post(full_url)
        if response.status_code == 200:
            print(f"API request successful: {endpoint}")
        else:
            print(f"API request failed with status code {response.status_code}: {endpoint}")

#LEDConnectorProviderRole()._controlLedOperation(argument = "off")

    