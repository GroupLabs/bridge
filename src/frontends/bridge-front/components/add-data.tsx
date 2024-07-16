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
import { TypeSelector } from "@/components/add-data-type-selector";
import { AddDataLinearTasks } from '@/components/add-data-linear-tasks';
import { PlusIcon } from "@radix-ui/react-icons";

export function AddData() {
  const [file, setFile] = useState<File | null>(null);
  const [selectedFileType, setSelectedFileType] = useState<string>("");

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
        <Button variant="outline">
          Add Data
        </Button>
      </DialogTrigger>
      <DialogContent className="">
        <DialogHeader>
          <DialogTitle>Upload Data</DialogTitle>
          <DialogDescription>
            Select the type of data you want to upload and then choose the file or enter details.
          </DialogDescription>
        </DialogHeader>
        <div className="">
          <TypeSelector
            value={selectedFileType}
            onChange={setSelectedFileType}
          />
        </div>
        {selectedFileType === "pdf" && (
          <>
            <div className="flex items-center justify-center">
              <Input 
                id="file" 
                type="file" 
                accept="application/pdf"
                onChange={handleFileChange} 
              />
            </div>
            <DialogFooter className="sm:justify-start">
              <DialogClose asChild>
                <Button type="button" variant="secondary" onClick={handleSubmit}>
                  Submit
                </Button>
              </DialogClose>
            </DialogFooter>
          </>
        )}
        {selectedFileType === "linear" && (
          <AddDataLinearTasks />
        )}
      </DialogContent>
    </Dialog>
  );
}