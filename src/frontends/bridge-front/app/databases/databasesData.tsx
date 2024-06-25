import postgresqlimg from '@/public/images/postgresql.png'
import azureimg from '@/public/images/azure.png'
import mongodbimg from '@/public/images/mongodb.svg'
import mysqlimg from '@/public/images/mysql.svg'

const databases = [
  {
    title: 'PostgreSQL',
    img: postgresqlimg,
    active: false
  },
  {
    title: 'Azure',
    img: azureimg,
    active: true
  },
  {
    title: 'MongoDB',
    img: mongodbimg,
    active: false
  },
  {
    title: 'MySQL',
    img: mysqlimg,
    active: false
  }
]

export default databases
