import githubimg from '@/public/images/github.svg'
import slackimg from '@/public/images/slack.svg'
import office365img from '@/public/images/office365.png'
import googledriveimg from '@/public/images/googledrive.svg'
import sapimg from '@/public/images/sap.svg'
import workdayimg from '@/public/images/workday.svg'
import salesforceimg from '@/public/images/salesforce.svg'
import { authenticateSlack } from '@/lib/actions/connector'

export interface Connector {
  title: string
  img: string
  active: boolean
  url?: Promise<string> | undefined
}

const connectors: Connector[] = [
  {
    title: 'Slack',
    img: slackimg,
    active: false,
    url: authenticateSlack()
  },
  {
    title: 'Office 365',
    img: office365img,
    active: false,
    url: undefined
  },
  {
    title: 'Google workspace',
    img: googledriveimg,
    active: false,
    url: undefined
  },
  {
    title: 'SAP',
    img: sapimg,
    active: false,
    url: undefined
  },
  {
    title: 'Workday',
    img: workdayimg,
    active: false,
    url: undefined
  },
  {
    title: 'Salesforce',
    img: salesforceimg,
    active: false,
    url: undefined
  },
  {
    title: 'Github',
    img: githubimg,
    active: false,
    url: undefined
  }
]

export default connectors