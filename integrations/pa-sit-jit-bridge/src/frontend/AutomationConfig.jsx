import { events } from "@forge/bridge";
import ForgeReconciler, { Text, useProductContext } from "@forge/react";
import React, { useEffect, useState } from "react";

import { AutomationInputsForm } from "./AutomationInputsForm.jsx";

function AutomationConfig() {
  const context = useProductContext();
  const [isValidating, setIsValidating] = useState(false);

  useEffect(() => {
    const subscription = events.on(
      "AUTOMATION_ACTION_VALIDATE_RULE_EVENT",
      ({ isValidating: validating }) => setIsValidating(validating),
    );
    return () => subscription.then((listener) => listener.unsubscribe());
  }, []);

  if (!context) {
    return <Text>Loading action configuration...</Text>;
  }

  return <AutomationInputsForm context={context} isValidating={isValidating} />;
}

ForgeReconciler.render(
  <React.StrictMode>
    <AutomationConfig />
  </React.StrictMode>,
);
