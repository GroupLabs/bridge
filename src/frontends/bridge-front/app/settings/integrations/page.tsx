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

export const metadata: Metadata = {
  title: "Integrations",
  description: "See all the integrations that are logged in Bridge.",
}

interface IntegrationsInterface {
  task_id?: string;
  filename?: string;
  status?: string;
  type?: string;
}

async function getIntegrations() {

  //
  // TODO
  // Is this optimal? Should the server process these requests? Should it be cached?
  //
  //

  const url = process.env.BRIDGE_URL;

  if (!url) {
    throw new Error('BRIDGE_URL is not defined');
  }

  try {
    const response = await fetch(`${url}/integrations/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      throw new Error(`Error: ${response.status}`);
    }

    const textData = await response.text();

    let parsedData;
    try {
      parsedData = JSON.parse(textData);
    } catch (jsonError) {
      console.error('Error parsing JSON:', jsonError);
      throw new Error('Failed to parse JSON response');
    }

    if (!parsedData.tasks) {
      console.error('No tasks found in the response:', parsedData);
      throw new Error('No tasks found in the response');
    }

    if (parsedData.tasks.length === 0) {
      console.warn('Tasks array is empty:', parsedData.tasks);
    }

    const tasks = (parsedData.tasks as IntegrationsInterface[]).map((task) => ({
      id: task.task_id ?? '',
      title: task.filename ?? '',
      status: task.status ?? '',
      label: task.type ?? '',
    }));

    return z.array(taskSchema).parse(tasks);
  } catch (error) {
    console.error('Error fetching integrations:', error);
    throw new Error('Failed to fetch integrations');
  }
}

export default async function IntegrationsPage() {
  const integrationsData = await getIntegrations()

  return (
    <>
      <div className="hidden h-full flex-1 flex-col space-y-8 md:flex">
        <div className="flex flex-col">
            <div className="flex items-center justify-between space-y-2">
              <h2 className="text-2xl font-bold tracking-tight">Integrations</h2>
              <AddData />
            </div>
            <p className="text-muted-foreground">
              Here are all the integrations that are logged in Bridge.
            </p>
          </div>
        <DataTable data={integrationsData} columns={columns} />
      </div>
    </>
  )
}