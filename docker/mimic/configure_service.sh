#!/bin/bash

SCRIPT="python register_backup_api.py"

SERVICE_NAME="Cloud Backup"
SERVICE_TYPE="rax:backup"
SERVICE_API_ADDRESS="${CLOUD_BACKUP_API}"
SERVICE_API_VERSION="${CLOUD_BACKUP_API_VERSION}"

REGION_DATA=""

if [ "${SERVICE_API_VERSION}" == "v1.0" ]; then
  REGION_DATA="DFW;http://${SERVICE_API_ADDRESS}/${SERVICE_API_VERSION}/%tenant_id%;http://${SERVICE_API_ADDRESS}/${SERVICE_API_VERSION}/%tenant_id%
ORD;http://${SERVICE_API_ADDRESS}/${SERVICE_API_VERSION}/%tenant_id%;http://${SERVICE_API_ADDRESS}/${SERVICE_API_VERSION}/%tenant_id%
IAD;http://${SERVICE_API_ADDRESS}/${SERVICE_API_VERSION}/%tenant_id%;http://${SERVICE_API_ADDRESS}/${SERVICE_API_VERSION}/%tenant_id%
"
else
  REGION_DATA="DFW;http://${SERVICE_API_ADDRESS}/${SERVICE_API_VERSION}/%tenant_id%;http://${SERVICE_API_ADDRESS}/${SERVICE_API_VERSION}/%tenant_id%
"
fi


${SCRIPT} services add

for REGION_INFO in ${REGION_DATA}
do
    REGION=`echo ${REGION_INFO} | cut -f 1 -d ';'`
    PUBLIC_URL=`echo ${REGION_INFO} | cut -f 2 -d ';'`
    SNET_URL=`echo ${REGION_INFO} | cut -f 3 -d ';'`

    template_id=`echo "Cloud Backup ${REGION}" | md5sum | cut -f 1 -d ' '`
    ${SCRIPT} templates add --name "${SERVICE_NAME}" --type "${SERVICE_TYPE}" --template-id ${template_id} --region "${REGION}" -p "${PUBLIC_URL}" -i "${SNET_URL}" -e 
done
