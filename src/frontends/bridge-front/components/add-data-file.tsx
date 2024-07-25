// components/add-data-file.tsx
'use client'
import { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

interface AddDataFileProps {
  onClose: () => void;
}

export const AddDataFile: React.FC<AddDataFileProps> = ({ onClose }) => {
  const [file, setFile] = useState<File | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = event.target.files;
    if (selectedFiles && selectedFiles.length > 0) {
      setFile(selectedFiles[0]);
    } else {
      setFile(null);
    }
  };

  const handleSubmit = async () => {
    if (!file) {
      toast("Please select a file first.");
      return;
    }

    try {
      const form = new FormData();
      form.append("file", file);

      const response = await fetch('/api/upload/file', {
        method: "POST",
        body: form,
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          toast("File uploaded successfully!");
          onClose();  // Close the dialog on successful upload
        } else {
          toast("File upload failed.");
        }
      } else {
        toast("File upload failed.");
      }
      setFile(null);
    } catch (error) {
      console.error("Error uploading file:", error);
      toast("An error occurred while uploading the file.");
    }
  };

  return (
    <>
      <div className="flex items-center justify-center">
        <Input 
          id="file" 
          type="file" 
          accept="
          text/plain, 
          application/rtf,
          application/msword,
          application/vnd.openxmlformats-officedocument.wordprocessingml.document,
          application/pdf,
          application/epub+zip,
          text/markdown,
          application/vnd.ms-powerpoint,
          application/vnd.openxmlformats-officedocument.presentationml.presentation
          "
          onChange={handleFileChange} 
        />
      </div>
      <Button type="button" variant="secondary" onClick={handleSubmit} className="mt-4">
        Submit
      </Button>
    </>
  );
};