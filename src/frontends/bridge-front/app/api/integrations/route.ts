// api/integrations/route.ts
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { taskSchema } from '@/lib/types/schema';

interface IntegrationsInterface {
  task_id?: string;
  filename?: string;
  status?: string;
  type?: string;
}

const url = process.env.BRIDGE_URL;

export async function GET() {
  if (!url) {
    return NextResponse.json({ error: 'BRIDGE_URL is not defined' }, { status: 500 });
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
      return NextResponse.json({ error: `Error: ${response.status}` }, { status: response.status });
    }

    const textData = await response.text();

    let parsedData;
    try {
      parsedData = JSON.parse(textData);
    } catch (jsonError) {
      console.error('Error parsing JSON:', jsonError);
      return NextResponse.json({ error: 'Failed to parse JSON response' }, { status: 500 });
    }

    if (!parsedData.tasks || parsedData.tasks.length === 0) {
      return NextResponse.json({ ids: [] });
    }

    const tasks = (parsedData.tasks as IntegrationsInterface[]).map((task) => ({
      id: task.task_id ?? '',
      title: task.filename ?? '',
      status: task.status ?? '',
      label: task.type ?? '',
    }));

    return NextResponse.json(z.array(taskSchema).parse(tasks));
  } catch (error) {
    console.error('Error fetching integrations:', error);
    return NextResponse.json({ error: 'Failed to fetch integrations' }, { status: 500 });
  }
}