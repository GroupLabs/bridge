import { promises as fs } from "fs"
import path from "path"
import { Metadata } from "next"
import Image from "next/image"
import { z } from "zod"

import { columns } from "@/components/ui/connector-table/columns"
import { DataTable } from "@/components/ui/connector-table/data-table"
import { UserNav } from "@/components/ui/connector-table/user-nav"
import { taskSchema } from "@/lib/types/schema"
import { AddData } from "@/components/add-data"
import { get } from "http"

export const metadata: Metadata = {
  title: "Integrations",
  description: "A task and issue tracker build using Tanstack Table.",
}

// Simulate a database read for tasks.
async function getIntegrations() {
  const data = await fs.readFile(
    path.join(process.cwd(), "/lib/data/tasks.json")
  )

  const tasks = JSON.parse(data.toString())

  return z.array(taskSchema).parse(tasks)
}

export default async function IntegrationsPage() {
  const integrationsData = await getIntegrations()

  return (
    <>
      <div className="hidden h-full flex-1 flex-col space-y-8 md:flex">
        <div className="flex items-center justify-between space-y-2">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Integrations</h2>
            <p className="text-muted-foreground">
              Here are all the integrations that are logged in Bridge.
            </p>
          </div>
        </div>
        <DataTable data={integrationsData} columns={columns} />
      </div>
    </>
  )
}