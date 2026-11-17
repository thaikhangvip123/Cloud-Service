import React from "react";
import { view } from "@forge/bridge";
import {
  Box,
  ErrorMessage,
  Form,
  Stack,
  Text,
  Textfield,
  useForm,
} from "@forge/react";

export function AutomationInputsForm({ context, isValidating }) {
  const form = useForm({
    defaultValues: context.extension?.data?.inputs ?? {},
    disabled: isValidating,
  });
  const { formState, getValues, handleSubmit, register } = form;

  const submitUpdatedValues = (input) => {
    view.submit({ ...getValues(), ...input });
  };

  const { onChange: requestIdOnChange, ...requestIdProps } = register("requestId", {
    required: { value: true, message: "Request ID is required" },
    disabled: isValidating,
  });
  const { onChange: requesterOnChange, ...requesterProps } = register("requester", {
    required: { value: true, message: "Requester email is required" },
    disabled: isValidating,
  });
  const { onChange: awsAccountOnChange, ...awsAccountProps } = register("awsAccount", {
    required: { value: true, message: "AWS account name is required" },
    disabled: isValidating,
  });
  const { onChange: accessTypeOnChange, ...accessTypeProps } = register("accessType", {
    required: { value: true, message: "Access type is required" },
    disabled: isValidating,
  });
  const { onChange: durationHoursOnChange, ...durationHoursProps } = register("durationHours", {
    required: { value: true, message: "Duration hours is required" },
    disabled: isValidating,
  });

  return (
    <Box>
      <Form onSubmit={handleSubmit((data) => view.submit(data))}>
        <Stack space="space.200">
          <Text>Request ID</Text>
          <Textfield
            {...requestIdProps}
            onChange={(event) => {
              requestIdOnChange(event);
              submitUpdatedValues({ requestId: event.target.value });
            }}
          />
          {formState.errors.requestId?.message && (
            <ErrorMessage>{formState.errors.requestId.message}</ErrorMessage>
          )}

          <Text>Requester email</Text>
          <Textfield
            {...requesterProps}
            onChange={(event) => {
              requesterOnChange(event);
              submitUpdatedValues({ requester: event.target.value });
            }}
          />
          {formState.errors.requester?.message && (
            <ErrorMessage>{formState.errors.requester.message}</ErrorMessage>
          )}

          <Text>AWS account name</Text>
          <Textfield
            {...awsAccountProps}
            onChange={(event) => {
              awsAccountOnChange(event);
              submitUpdatedValues({ awsAccount: event.target.value });
            }}
          />
          {formState.errors.awsAccount?.message && (
            <ErrorMessage>{formState.errors.awsAccount.message}</ErrorMessage>
          )}

          <Text>Access type</Text>
          <Textfield
            {...accessTypeProps}
            onChange={(event) => {
              accessTypeOnChange(event);
              submitUpdatedValues({ accessType: event.target.value });
            }}
          />
          {formState.errors.accessType?.message && (
            <ErrorMessage>{formState.errors.accessType.message}</ErrorMessage>
          )}

          <Text>Duration hours</Text>
          <Textfield
            {...durationHoursProps}
            onChange={(event) => {
              durationHoursOnChange(event);
              submitUpdatedValues({ durationHours: event.target.value });
            }}
          />
          {formState.errors.durationHours?.message && (
            <ErrorMessage>{formState.errors.durationHours.message}</ErrorMessage>
          )}
        </Stack>
      </Form>
    </Box>
  );
}
