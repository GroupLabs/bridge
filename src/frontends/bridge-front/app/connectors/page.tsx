import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FileUp, Database, HardDrive, Globe } from 'lucide-react';

const connections = [
  {
    user: { name: "Michael Foster", avatar: "https://images.unsplash.com/photo-1519244703995-f4e0f30006d5?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format&fit=facearea&facepad=2&w=256&h=256&q=80" },
    commit: { hash: "2d89f0c8", branch: "main" },
    status: "Completed",
    type: "Database",
    duration: "25s",
    deployedAt: "2023-01-23T11:00",
  },
  {
    user: { name: "Lindsay Walton", avatar: "https://images.unsplash.com/photo-1517841905240-472988babdf9?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format&fit=facearea&facepad=2&w=256&h=256&q=80" },
    commit: { hash: "249df660", branch: "main" },
    status: "Completed",
    type: "Filesystem",
    duration: "1m 32s",
    deployedAt: "2023-01-23T09:00",
  },
  {
    user: { name: "Courtney Henry", avatar: "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format&fit=facearea&facepad=2&w=256&h=256&q=80" },
    commit: { hash: "11464223", branch: "main" },
    status: "Error",
    type: "API",
    duration: "1m 4s",
    deployedAt: "2023-01-23T00:00",
  },
  {
    user: { name: "Tom Cook", avatar: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format&fit=facearea&facepad=2&w=256&h=256&q=80" },
    commit: { hash: "dad28e95", branch: "main" },
    status: "Completed",
    type: "Database",
    duration: "2m 15s",
    deployedAt: "2023-01-21T13:00",
  },
  {
    user: { name: "Whitney Francis", avatar: "https://images.unsplash.com/photo-1517365830460-955ce3ccd263?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format&fit=facearea&facepad=2&w=256&h=256&q=80" },
    commit: { hash: "5c1fd07f", branch: "main" },
    status: "Completed",
    type: "Filesystem",
    duration: "37s",
    deployedAt: "2023-01-09T08:45",
  },
];

export default function ConnectorsPage() {
  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-6">Connectors</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <Card>
          <CardHeader>
            <CardTitle>Storage</CardTitle>
            <CardDescription>Immutable file storage</CardDescription>
          </CardHeader>
          <CardContent>
            <Button className="w-full flex items-center justify-center">
              <FileUp className="mr-2 h-4 w-4" /> Create new file object
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Connections</CardTitle>
            <CardDescription>Connect to</CardDescription>
          </CardHeader>
          <CardContent>
            <Button className="w-full flex items-center justify-center">
              <Database className="mr-2 h-4 w-4" /> Connect to database, filesystem, slack, etc.
            </Button>
          </CardContent>
        </Card>
      </div>
      
      <div className="bg-gray-900 py-10 rounded-xl">
        <h2 className="px-4 text-base font-semibold leading-7 text-white sm:px-6 lg:px-8">Existing connections</h2>
        <table className="mt-6 w-full whitespace-nowrap text-left">
          <colgroup>
            <col className="w-full sm:w-4/12" />
            <col className="lg:w-4/12" />
            <col className="lg:w-2/12" />
            <col className="lg:w-1/12" />
            <col className="lg:w-1/12" />
          </colgroup>
          <thead className="border-b border-white/10 text-sm leading-6 text-white">
            <tr>
              <th scope="col" className="py-2 pl-4 pr-8 font-semibold sm:pl-6 lg:pl-8">User</th>
              <th scope="col" className="hidden py-2 pl-0 pr-8 font-semibold sm:table-cell">Commit</th>
              <th scope="col" className="py-2 pl-0 pr-4 text-right font-semibold sm:pr-8 sm:text-left lg:pr-20">Status</th>
              <th scope="col" className="hidden py-2 pl-0 pr-8 font-semibold md:table-cell lg:pr-20">Duration</th>
              <th scope="col" className="hidden py-2 pl-0 pr-4 text-right font-semibold sm:table-cell sm:pr-6 lg:pr-8">Deployed at</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {connections.map((connection, index) => (
              <tr key={index}>
                <td className="py-4 pl-4 pr-8 sm:pl-6 lg:pl-8">
                  <div className="flex items-center gap-x-4">
                    <img src={connection.user.avatar} alt="" className="h-8 w-8 rounded-full bg-gray-800" />
                    <div className="truncate text-sm font-medium leading-6 text-white">{connection.user.name}</div>
                  </div>
                </td>
                <td className="hidden py-4 pl-0 pr-4 sm:table-cell sm:pr-8">
                  <div className="flex gap-x-3">
                    <div className="font-mono text-sm leading-6 text-gray-400">{connection.commit.hash}</div>
                    <div className="rounded-md bg-gray-700/40 px-2 py-1 text-xs font-medium text-gray-400 ring-1 ring-inset ring-white/10">{connection.commit.branch}</div>
                  </div>
                </td>
                <td className="py-4 pl-0 pr-4 text-sm leading-6 sm:pr-8 lg:pr-20">
                  <div className="flex items-center justify-end gap-x-2 sm:justify-start">
                    <div className="flex-none rounded-full p-1 text-green-400">
                      <div className="h-1.5 w-1.5 rounded-full bg-current"></div>
                    </div>
                    <div className="hidden text-white sm:block">{connection.status}</div>
                  </div>
                </td>
                <td className="hidden py-4 pl-0 pr-8 text-sm leading-6 text-gray-400 md:table-cell lg:pr-20">{connection.duration}</td>
                <td className="hidden py-4 pl-0 pr-4 text-right text-sm leading-6 text-gray-400 sm:table-cell sm:pr-6 lg:pr-8">
                  <time dateTime={connection.deployedAt}>
                    {new Date(connection.deployedAt).toLocaleString()}
                  </time>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}