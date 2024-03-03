import os

from magika import Magika

magika = Magika()

def get_pathtype(filepath: str):

    if os.path.exists(filepath):
        if os.path.isdir(filepath):
            return 'dir'
        else:
            with open(filepath, 'rb') as file:
                file_bytes = file.read()
                return magika.identify_bytes(file_bytes).output.ct_label
    else:
        return None



if __name__ == "__main__":
    print(get_pathtype("api.py"))
    

# result = magika.identify_bytes(b"# Example\nThis is an example of markdown!")
# print(result.output.ct_label)