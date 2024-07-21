'use client';

import { useEffect, useState } from 'react';
import Head from 'next/head';
import { columns } from '@/components/ui/connector-table/columns';
import { DataTable } from '@/components/ui/connector-table/data-table';
import { AddData } from '@/components/add-data';

async function fetchIntegrations() {
  const res = await fetch('/api/integrations/', {
    method: "GET",
  });
  const data = await res.json();
  if (!res.ok || !data) {
    throw new Error('Failed to fetch integrations');
  }
  return data;
}

export default function IntegrationsPage() {
  const [integrationsData, setIntegrationsData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchIntegrations()
      .then(setIntegrationsData)
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return <div>Error loading integrations: {error}</div>;
  }

  return (
    <>
      <Head>
        <title>Integrations</title>
        <meta name="description" content="See all the integrations that are logged in Bridge." />
      </Head>
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
        {integrationsData ? (
          <DataTable data={integrationsData} columns={columns} />
        ) : (
          <div>Loading...</div>
        )}
      </div>
    </>
  );
}