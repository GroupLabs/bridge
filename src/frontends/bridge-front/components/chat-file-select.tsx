"use client";

// Inspired by https://github.com/mxkaske/mxkaske.dev/blob/main/components/craft/fancy-multi-select.tsx

import * as React from "react";
import { X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Command,
  CommandGroup,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog"
import { Command as CommandPrimitive } from "cmdk";

interface FileData {
  value: string;
  label: string;
}

// Fetch function to get files from the server
async function fetchFiles(): Promise<FileData[]> {
  try {
    const response = await fetch('/api/fetchfiles', {
      cache: 'no-store',
    });
    const data = await response.json();
    if (!data || !Array.isArray(data.ids)) {
      return [];
    }
    return data.ids;
  } catch (error) {
    console.error("Error fetching files:", error);
    return [];
  }
}

// FileSelect component
interface FileSelectProps {
  onFilesSelected: (selectedFiles: FileData[]) => void;
}

export function FileSelect({ onFilesSelected }: FileSelectProps) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [open, setOpen] = React.useState(false);
  const [selected, setSelected] = React.useState<FileData[]>([]);
  const [inputValue, setInputValue] = React.useState("");
  const [files, setFiles] = React.useState<FileData[]>([]);

  React.useEffect(() => {
    fetchFiles().then(setFiles);
  }, []);

  React.useEffect(() => {
    onFilesSelected(selected);
  }, [selected, onFilesSelected]);

  const handleUnselect = React.useCallback((file: FileData) => {
    setSelected((prev) => prev.filter((s) => s.value !== file.value));
  }, []);

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      const input = inputRef.current;
      if (input) {
        if (e.key === "Delete" || e.key === "Backspace") {
          if (input.value === "") {
            setSelected((prev) => {
              const newSelected = [...prev];
              newSelected.pop();
              return newSelected;
            });
          }
        }
        if (e.key === "Escape") {
          input.blur();
        }
      }
    },
    []
  );

  const selectables = files.filter((file) => !selected.includes(file));

  return (

    <Dialog>
      <DialogTrigger asChild>
        <Button variant="link">{selected.length > 0 ? `${selected.length} file(s) selected` : 'select files'}</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Edit profile</DialogTitle>
          <DialogDescription>
            Make changes to your profile here. Click save when you&apos;re done.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <Command onKeyDown={handleKeyDown} className="overflow-visible bg-transparent">
            <div className="group rounded-md border border-input px-3 py-2 text-sm ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2">
              <div className="flex flex-wrap gap-1">
                {selected.map((file) => (
                  <Badge key={file.value} variant="secondary">
                    {file.label}
                    <button
                      className="ml-1 rounded-full outline-none ring-offset-background focus:ring-2 focus:ring-ring focus:ring-offset-2"
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          handleUnselect(file);
                        }
                      }}
                      onMouseDown={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                      }}
                      onClick={() => handleUnselect(file)}
                    >
                      <X className="h-3 w-3 text-muted-foreground hover:text-foreground" />
                    </button>
                  </Badge>
                ))}
                <CommandPrimitive.Input
                  ref={inputRef}
                  value={inputValue}
                  onValueChange={setInputValue}
                  onBlur={() => setOpen(false)}
                  onFocus={() => setOpen(true)}
                  placeholder="Select files..."
                  className="ml-2 flex-1 bg-transparent outline-none placeholder:text-muted-foreground"
                />
              </div>
            </div>
            <div className="relative mt-2">
              <CommandList>
                {open && selectables.length > 0 ? (
                  <div className="absolute top-0 z-10 w-full rounded-md border bg-popover text-popover-foreground shadow-md outline-none animate-in">
                    <CommandGroup className="h-full overflow-auto">
                      {selectables.map((file) => (
                        <CommandItem
                          key={file.value}
                          onMouseDown={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                          }}
                          onSelect={() => {
                            setInputValue("");
                            setSelected((prev) => [...prev, file]);
                          }}
                          className={"cursor-pointer"}
                        >
                          {file.label}
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </div>
                ) : null}
              </CommandList>
            </div>
          </Command>
        </div>
        <DialogFooter>
        <DialogClose asChild>
            <Button type="button">
              Apply
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>





    
  );
}