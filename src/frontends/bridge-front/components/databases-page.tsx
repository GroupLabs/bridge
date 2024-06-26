'use client'

import { cn } from '@/lib/utils'
import { AnimatePresence, motion } from 'framer-motion'
import { useState } from 'react'
import { Card, CardHeader, CardContent, CardFooter } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import Image from 'next/image'
import { AddDatabaseModal } from '@/components/add-database-modal'
import { ModifyDatabaseModal } from '@/components/modify-database-modal'
import { Database } from '@/app/databases/databasesData'

export const DatabasesPage = ({
  items,
  className
}: {
  items: Database[]
  className?: string
}) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)

  return (
    <div
      className={cn(
        'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 py-10',
        className
      )}
    >
      {items.map((item, idx) => (
        <div
          key={item.title}
          className="relative group block p-2 h-full w-full"
          onMouseEnter={() => setHoveredIndex(idx)}
          onMouseLeave={() => setHoveredIndex(null)}
        >
          <AnimatePresence>
            {hoveredIndex === idx && (
              <motion.span
                className="absolute inset-0 h-full w-full bg-neutral-200 dark:bg-slate-800/[0.8] block rounded-3xl"
                layoutId="hoverBackground"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1, transition: { duration: 0.15 } }}
                exit={{
                  opacity: 0,
                  transition: { duration: 0.15, delay: 0.2 }
                }}
              />
            )}
          </AnimatePresence>
          <Card className="rounded-2xl h-full w-full p-4 overflow-hidden dark:bg-black border border-transparent dark:border-white/[0.2] group-hover:border-slate-700 relative z-20">
            <CardHeader>
              <div className="flex flex-row items-center justify-between">
                <div className="flex items-center gap-3">
                  <Image src={item.img} alt="logo" className="h-6 w-6" />
                </div>
                <div>
                  <Switch disabled defaultChecked={item.active} />
                </div>
              </div>
              <span className="text-lg font-medium">{item.title}</span>
            </CardHeader>
            <CardFooter>
              {item.active ? (
                <ModifyDatabaseModal
                  connectionDetails={{
                    ...item.connectionDetails,
                    db_type: item.db_type
                  }}
                />
              ) : (
                <AddDatabaseModal />
              )}
            </CardFooter>
          </Card>
        </div>
      ))}
    </div>
  )
}
