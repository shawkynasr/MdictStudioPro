from abc import ABC, abstractmethod

class BaseConverterPlugin(ABC):
    # --- INTERNAL REGISTRATION ---
    # A stable, unique identifier for the plugin (e.g., "moe_revised_dict")
    # This prevents silent overwrites if two plugins share the same 'name'.
    id = None 

    # --- UI METADATA ---
    name = "Base Converter"
    description = "Abstract base class for dictionary converters."
    file_filter = "All Files (*.*)"
    default_encodings = ["utf-8"]
    
    # --- FUTURE PROOFING ---
    # Define custom UI options here later without breaking existing plugins.
    options_schema = [] 

    @abstractmethod
    def convert(self, input_file: str, output_file: str, encoding: str, progress_callback, log_callback) -> str:
        """
        Executes the conversion process.
        Must be implemented by all child classes.
        """
        pass