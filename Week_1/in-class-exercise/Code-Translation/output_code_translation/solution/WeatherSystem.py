class WeatherSystem:
    def __init__(self, city):
        self.city = city
        self.temperature = 0.0
        self.weather = ""
        self.weather_list = {}

    def query(self, weather_list, tmp_units="celsius"):
        self.weather_list = weather_list
        if self.city not in self.weather_list:
            return (0.0, "")
        else:
            info = self.weather_list[self.city]
            self.temperature = info["temperature"]
            self.weather = info["weather"]

        if info["temperature_units"] != tmp_units:
            if tmp_units == "celsius":
                return (self.fahrenheit_to_celsius(), self.weather)
            elif tmp_units == "fahrenheit":
                return (self.celsius_to_fahrenheit(), self.weather)
        else:
            return (self.temperature, self.weather)

    def set_city(self, city):
        self.city = city

    def set_temperature(self, temperature):
        self.temperature = temperature

    def celsius_to_fahrenheit(self):
        return (self.temperature * 9 / 5) + 32

    def fahrenheit_to_celsius(self):
        return (self.temperature - 32) * 5 / 9

    def get_city(self):
        return self.city
