import os

from magika import Magika
import re

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

def parse_connection_string(conn_string):
    # Extended pattern to match more complex connection strings, with optional port and database
    pattern = r'(?P<type>\w+)://(?P<user>[^:@\/]+):(?P<password>[^:@\/]+)@(?P<host>[^:\/]+)(?::(?P<port>\d+))?(/(?P<database>[^\/]+)?)?'

    # Match the connection string against the pattern
    match = re.match(pattern, conn_string)

    if match:
        return {
            'database_type': match.group('type'),
            'host': match.group('host'),
            'user': match.group('user'),
            'password': match.group('password'),
            'port': match.group('port') if match.group('port') else None,
            'database': match.group('database') if match.group('database') else None
        }
    else:
        return None

if __name__ == "__main__":
    print(get_pathtype("api.py"))

    conn_string = 'postgres://username:password@localhost'
    parsed = parse_connection_string(conn_string)
    print(parsed)
    
    conn_string = 'mysql://user:password@localhost:3306/mydatabase'
    parsed = parse_connection_string(conn_string)
    print(parsed)
    
    # result = magika.identify_bytes(b"# Example\nThis is an example of markdown!")
    # print(result.output.ct_label)