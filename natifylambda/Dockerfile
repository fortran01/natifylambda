FROM public.ecr.aws/lambda/python:3.8

# Copy function code and requirements
COPY natifylambda/ ${LAMBDA_TASK_ROOT}

# Install the function's dependencies
RUN python3.8 -m pip install -r ${LAMBDA_TASK_ROOT}/requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Set the CMD to your handler (could be a function)
CMD ["natifylambda.handler"]
