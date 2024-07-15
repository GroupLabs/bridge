import { ModeToggle } from "@/components/mode-toggle"
import { Separator } from "@/components/ui/separator"

export default function GeneralSettings() {
  return (
    <div>
      <div>
        About (v0.2.8)
        <div className="py-6 font-mono text-sm">
          This is the pre-release version of the Bridge UI. It is not yet ready for production use.
        </div>
      </div>
      <Separator className="my-4" />
      <div className="flex flex-row items-center">
        <h1 className="mr-4">Theme</h1>
        <ModeToggle />
      </div>
    </div>
  )
}