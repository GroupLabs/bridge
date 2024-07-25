'use client'
import { useState } from 'react';
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { TypeSelector } from "@/components/add-data-type-selector";
import { AddDataLinearTasks } from '@/components/add-data-linear-tasks';
import { AddDataFile } from '@/components/add-data-file';

export function AddData() {
  const [selectedFileType, setSelectedFileType] = useState<string>("");
  const [isDialogOpen, setIsDialogOpen] = useState<boolean>(false);

  const handleCloseDialog = () => {
    setIsDialogOpen(false);
  };

  return (
    <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" onClick={() => setIsDialogOpen(true)}>
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
        {selectedFileType === "file" && (
          <AddDataFile onClose={handleCloseDialog} />
        )}
        {selectedFileType === "linear" && (
          <AddDataLinearTasks onClose={handleCloseDialog} />
        )}
      </DialogContent>
    </Dialog>
  );
}