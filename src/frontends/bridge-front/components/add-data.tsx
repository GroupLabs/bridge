'use client'
import { useState } from 'react';
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

export function AddData() {
  const [file, setFile] = useState(null);

  const handleFileChange = (event: any) => {
    setFile(event.target.files[0]);
  };

  const handleSubmit = async () => {
    if (!file) {
      toast("Please select a file first.");
      return;
    }

    try {
      const form = new FormData();
      form.append("file", file);

      const response = await fetch('/api/upload', {
        method: "POST",
        body: form,
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          toast("File uploaded successfully!");
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
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline">Upload File</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Upload PDF File</DialogTitle>
          <DialogDescription>
            Anyone who has this link will be able to view added data.
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-center justify-center my-4">
          <Input id="file" type="file" accept='.pdf' onChange={handleFileChange} />
        </div>
        <DialogFooter className="sm:justify-start">
        <DialogClose asChild>
            <Button type="button" variant="secondary" onClick={handleSubmit}>
              Submit
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}