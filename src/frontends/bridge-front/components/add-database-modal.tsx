import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { pingDatabase, DatabaseConnectionDetails } from '@/lib/actions/database'
import { cn } from '@/lib/utils'

interface AddDatabaseModalProps {
  className?: string
}

export function AddDatabaseModal({ className }: AddDatabaseModalProps) {
  const [loading, setLoading] = useState(false)

  const [connectionData, setConnectionData] =
    useState<DatabaseConnectionDetails>({
      db_type: ''
    })
  const [pingResult, setPingResult] = useState<string | null>(null)

  const handleSaveChanges = async () => {
    setLoading(true) // Step 2: Set loading to true when operation starts
    const result = await pingDatabase(connectionData)
    setPingResult(result)
    setLoading(false) // Set loading to false when operation finishes
  }

  const handleTypeChange = (value: string) => {
    setConnectionData(prev => ({ ...prev, database: value }))
  }

  const handleConnectionStringChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setConnectionData(prev => ({
      ...prev,
      connectionString: event.target.value
    }))
  }

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { id, value } = event.target
    setConnectionData(prev => ({ ...prev, [id]: value }))
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        {/* <Button variant={'default'} className="w-full">
          Add Database
        </Button> */}
        <div
          className={cn(
            'flex items-center justify-center h-full w-full text-7xl hover:cursor-pointer',
            className
          )}
        >
          <LoadingSpinner />
        </div>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Database</DialogTitle>
          <DialogDescription>
            Connect a new database to integrate with your data sources.
          </DialogDescription>
        </DialogHeader>
        <Tabs defaultValue="string">
          <TabsList>
            <TabsTrigger value="string">Connection String</TabsTrigger>
            <TabsTrigger value="credentials">Credentials</TabsTrigger>
          </TabsList>
          <TabsContent value="string">
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="type" className="text-right">
                  Type
                </Label>
                <Select onValueChange={value => handleTypeChange(value)}>
                  <SelectTrigger id="type" className="col-span-3">
                    <SelectValue placeholder="" />
                  </SelectTrigger>
                  <SelectContent position="popper">
                    <SelectItem value="mongodb">MongoDB</SelectItem>
                    <SelectItem value="azure">Azure</SelectItem>
                    <SelectItem value="postgresql">PostgreSQL</SelectItem>
                    <SelectItem value="mysql">Mysql</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Separator />
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="connectionString" className="text-right">
                  Connection String
                </Label>
                <Input
                  id="connectionString"
                  onChange={handleConnectionStringChange}
                  className="col-span-3"
                />
              </div>
            </div>
          </TabsContent>
          <TabsContent value="credentials">
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="type" className="text-right">
                  Type
                </Label>
                <Select onValueChange={value => handleTypeChange(value)}>
                  <SelectTrigger id="type" className="col-span-3">
                    <SelectValue placeholder="" />
                  </SelectTrigger>
                  <SelectContent position="popper">
                    <SelectItem value="mongodb">MongoDB</SelectItem>
                    <SelectItem value="azure">Azure</SelectItem>
                    <SelectItem value="postgresql">PostgreSQL</SelectItem>
                    <SelectItem value="mysql">Mysql</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Separator />
              <div className="grid gap-4">
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="host" className="text-right">
                    Host
                  </Label>
                  <Input
                    id="host"
                    onChange={handleInputChange}
                    className="col-span-3"
                  />
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="username" className="text-right">
                    Username
                  </Label>
                  <Input
                    id="username"
                    onChange={handleInputChange}
                    className="col-span-3"
                  />
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="password" className="text-right">
                    Password
                  </Label>
                  <Input
                    id="password"
                    onChange={handleInputChange}
                    className="col-span-3"
                  />
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
        {loading ? (
          <LoadingSpinner /> // Step 3: Display LoadingSpinner when loading
        ) : (
          pingResult && <div>{pingResult}</div>
        )}
        <DialogFooter>
          <Button type="button" onClick={handleSaveChanges}>
            Save changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function LoadingSpinner() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="100"
      height="100"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn('')}
    >
      <path d="M12 8 L12 16 M8 12 L16 12" />
    </svg>
  )
}
