import { NotificationSettings } from "./DesktopNotifications";
import { PortableCredentials } from "./PortableCredentials";

export function DesktopGeneralSettings() {
  return (
    <>
      <PortableCredentials />
      <NotificationSettings />
    </>
  );
}
