from  allowed_extensions import AllowedExtensions 
import os
import pandas as pd

class Metadata:
    def __init__(self):
        self._name = None
        self._extension = None
        self._is_structured = None
        self._description = None
        self._contents = None
        
    def __repr__(self) -> str:
        r = ''
        r = r + f"name: {self._name}\n"
        r = r + f"ext: {self._extension}\n"
        r = r + f"structured: {self._is_structured}\n"
        r = r + f"description: {self._description}\n"
        r = r + f"contents: {self._contents}"
        
        return r
    
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value

    @property
    def extension(self):
        return self._extension

    @extension.setter
    def extension(self, value: str):
        if value not in AllowedExtensions.__members__:
            raise ValueError("Extension must be one of: " + ", ".join(AllowedExtensions.__members__))
        
        self._extension = AllowedExtensions[value].value
        
    @property
    def is_structured(self):
        return self._is_structured

    @is_structured.setter
    def is_structured(self, value: bool):
        self._is_structured = value
        
        
    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, value: str):
        self._description = value    
        
    @property
    def contents(self):
        return self._contents

    @contents.setter
    def contents(self, value):
        self._contents = value    
        
        
    
    def as_object(self):
        obj = {}
        obj["name"] = self._name
        obj["extension"] = self._extension
        obj["structured"] = self._is_structured
        obj["description"] = self._description
        obj["contents"] = self._contents
        
        return obj
    
    def csv_extraction(self, name, input):
        df_dict = {}
        df = pd.read_csv(input, encoding = 'latin-1')
        df_keys = []
        for column in df.columns.tolist():
            if ("id") in column.lower():
                df_keys.append(column)
        df_dict[name] = {"columns" : df.columns.tolist(),
                "keys": df_keys}
        return df_dict


    def metadata(input):
        
        metadata = Metadata()
        
        if isinstance(input, str):
            if os.path.exists(input):
                file_name = os.path.basename(input) # Gets rid of file path if a file path is used
                dir_path = os.path.dirname(input) # Need dir path
                name, ext = os.path.splitext(file_name)
                if (ext == '.desc'):
                    return
                
                metadata.name = name
                
                # get description from desc file
                # This doesn't seem to work for now, takes all file and assumes they are .desc
                if os.path.exists(f'{dir_path}/{name}.desc'):
                    with open(f'{dir_path}/{name}.desc', 'r') as f:
                        metadata.description = f.read()
                else: 
                    print(f"No description file provided for {name}{ext}")
                    metadata.description = "No description file provided"
                
                # structured
                if ext.lower() == '.csv':
                    metadata.extension = "CSV"
                    metadata.is_structured = True
                    df_dict = metadata.csv_extraction(name, input)
                    metadata.contents = df_dict
                    ## Add columns variable to metadata for csvs
                elif ext.lower() == '.tsv':
                    metadata.extension = "TSV"
                    metadata.is_structured = True
                elif ext.lower() == '.parquet':
                    metadata.extension = "PARQUET"
                    metadata.is_structured = True
                
                # unstructured
                elif ext.lower() == '.txt':
                    metadata.extension = "TXT"
                    metadata.is_structured = False
                elif ext.lower() == '.pdf':
                    metadata.extension = "PDF"
                    metadata.is_structured = False

                # if unstructured:
                # store a new vs, content is vecstore fp
                # else
                # store columns in content

                else:
                    raise NotImplementedError(f"WARN: Unsupported {ext} extension.")
            else:
                raise ValueError("Input to metadata function is a string but not a file path.")
        return metadata
