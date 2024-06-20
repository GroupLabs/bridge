'use client'

import { ConnectorsPage } from '@/components/connectors-page'
import { Separator } from '@/components/ui/separator'
import githubimg from '@/public/images/github.svg'
import slackimg from '@/public/images/slack.svg'
import office365img from '@/public/images/office365.png'
import googledriveimg from '@/public/images/googledrive.svg'
import sapimg from '@/public/images/sap.png'
import workdayimg from '@/public/images/workday.svg'
import salesforceimg from '@/public/images/salesforce.svg'

const Home = () => {
  return (
    <div className="max-w-5xl mx-auto px-8">
      <h1 className="text-center text-5xl mt-12">Connectors</h1>
      <Separator />
      <ConnectorsPage items={connectors} />
    </div>
  )
}

export const connectors = [
  {
    title: 'Slack',
    img: slackimg,
    active: false
  },
  {
    title: 'Office 365',
    img: office365img,
    active: true
  },
  {
    title: 'Google workspace',
    img: googledriveimg,
    active: false
  },
  {
    title: 'SAP',
    img: sapimg,
    active: false
  },
  {
    title: 'Workday',
    img: workdayimg,
    active: true
  },
  {
    title: 'Salesforce',
    img: salesforceimg,
    active: false
  },
  {
    title: 'Github',
    img: githubimg,
    active: true
  }
]

export default Home
