import React, { useState, ChangeEvent } from 'react'
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

interface ModifyDatabaseModalProps {
  connectionDetails: DatabaseConnectionDetails | null
}

export function ModifyDatabaseModal({
  connectionDetails
}: ModifyDatabaseModalProps) {
  const [loading, setLoading] = useState(false)
  const [connectionData, setConnectionData] =
    useState<DatabaseConnectionDetails>(
      connectionDetails || {
        db_type: '',
        connection_string: '',
        host: '',
        user: '',
        password: ''
      }
    )
  const [pingResult, setPingResult] = useState<string | null>(null)

  const handleSaveChanges = async () => {
    setLoading(true)
    const result = await pingDatabase(connectionData)
    setPingResult(result)
    setLoading(false)
  }

  const handleTypeChange = (value: string) => {
    setConnectionData(prev => ({ ...prev, db_type: value }))
  }

  const handleConnectionStringChange = (
    event: ChangeEvent<HTMLInputElement>
  ) => {
    setConnectionData(prev => ({
      ...prev,
      connection_string: event.target.value
    }))
  }

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const { id, value } = event.target
    setConnectionData(prev => ({ ...prev, [id]: value }))
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" className="w-full">
          Modify Database
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Modify Database</DialogTitle>
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
                <Label htmlFor="db_type" className="text-right">
                  Type
                </Label>
                <Select
                  onValueChange={handleTypeChange}
                  defaultValue={connectionData.db_type}
                >
                  <SelectTrigger id="db_type" className="col-span-3">
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
                <Label htmlFor="connection_string" className="text-right">
                  Connection String
                </Label>
                <Input
                  id="connection_string"
                  onChange={handleConnectionStringChange}
                  className="col-span-3"
                  value={connectionData.connection_string}
                />
              </div>
            </div>
          </TabsContent>
          <TabsContent value="credentials">
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="db_type" className="text-right">
                  Type
                </Label>
                <Select
                  onValueChange={handleTypeChange}
                  defaultValue={connectionData.db_type}
                >
                  <SelectTrigger id="db_type" className="col-span-3">
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
                    value={connectionData.host}
                  />
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <Label htmlFor="user" className="text-right">
                    Username
                  </Label>
                  <Input
                    id="user"
                    onChange={handleInputChange}
                    className="col-span-3"
                    value={connectionData.user}
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
                    value={connectionData.password}
                  />
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
        {loading ? <LoadingSpinner /> : pingResult && <div>{pingResult}</div>}
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
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn('animate-spin')}
    >
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  )
}
