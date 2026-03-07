import re
text = "The local dimension is d=3.001."
dims = re.findall(r"(?:d|次元|dimension)(?:=|\s+)?([0-9.]+)", text.lower())
print(f"Text: {text}")
print(f"Dims: {dims}")

text2 = "d=3.001"
dims2 = re.findall(r"(?:d|次元|dimension)(?:=|\s+)?([0-9.]+)", text2.lower())
print(f"Text2: {text2}")
print(f"Dims2: {dims2}")
