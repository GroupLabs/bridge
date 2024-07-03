import githubimg from '@/public/images/github.svg'
import slackimg from '@/public/images/slack.svg'
import office365img from '@/public/images/office365.png'
import googledriveimg from '@/public/images/googledrive.svg'
import sapimg from '@/public/images/sap.svg'
import workdayimg from '@/public/images/workday.svg'
import salesforceimg from '@/public/images/salesforce.svg'
import { authenticateConnector, pingConnector } from '@/lib/actions/connector'

export interface Connector {
  title: string
  img: string
  active: Promise<boolean> | undefined
  url?: Promise<string> | undefined
}

const connectors: Connector[] = [
  {
    title: 'Slack',
    img: slackimg,
    active: pingConnector("slack_ping"),
    url: authenticateConnector("slack_auth")
  },
  {
    title: 'Office 365',
    img: office365img,
    active: pingConnector("office_ping"),
    url: authenticateConnector("office_auth")
  },
  {
    title: 'Google Drive',
    img: googledriveimg,
    active: pingConnector("google_drive_ping"),
    url: authenticateConnector("google_drive_auth")
  },
  {
    title: 'Google Workspace',
    img: googledriveimg,
    active: pingConnector("google_ping"),
    url: authenticateConnector("google_auth")
  },
  {
    title: 'SAP',
    img: sapimg,
    active: pingConnector("sap_ping"),
    url: undefined
  },
  {
    title: 'Workday',
    img: workdayimg,
    active: pingConnector("workday_ping"),
    url: undefined
  },
  {
    title: 'Salesforce',
    img: salesforceimg,
    active: pingConnector("salesforce_ping"),
    url: authenticateConnector("salesforce_auth")
  },
  {
    title: 'Github',
    img: githubimg,
    active: pingConnector("github_ping"),
    url: undefined
  }
]

export default connectors