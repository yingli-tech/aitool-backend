import requests
import json
import base64

from urllib.parse import urlsplit, urlunsplit


url = "https://spread.name/sheet/Ch-JZHaS1Jr33yDMpDzHjQD1JJAP5FHRF3LI221VGFm-12MzaYevvfCflDPkrrRlLppo/filters/?query=e30%3D&options=eyJyb3dzTGltaXQiOjUwMDAsImRlYWxUeXBlIjoiYXBwc3VtbyIsImR5bmFtaWNEYXRhIjp7InNoZWV0SGFzaCI6IjE4MDM3NTYzODciLCJTQ1BUYWJsZUxhdGVzdFVwZGF0ZVRpbWVzdGFtcCI6MTc4Nzk5ODI5MDUwOH0sInNlYXJjaCI6eyJlbmFibGVkIjp0cnVlLCJjb2x1bW5zIjpbIk5hbWUtIiwiUHJpY2UtIiwiQ2F0ZWdvcnktIiwiSGFzaHRhZy0iLCJMb25nZGVzY3JpcHRpb24tIl19LCJzb3J0aW5nIjp7ImVuYWJsZWQiOmZhbHNlLCJzaHVmZmxlIjpmYWxzZX0sInBhZ2luYXRpb24iOnsiZW5hYmxlZCI6dHJ1ZSwiaXRlbXNQZXJQYWdlIjoiMTAwIn0sImZpbHRlcnMiOnsiZW5hYmxlZCI6dHJ1ZSwidmFsdWVzIjpbeyJpZCI6Ik5hbWUtIiwidHlwZSI6Im11bHRpcGxlIn0seyJpZCI6IkNhdGVnb3J5LSIsInR5cGUiOiJtdWx0aXBsZSJ9LHsiaWQiOiJQcmljZS0iLCJ0eXBlIjoibXVsdGlwbGUifV19LCJtYXBWaWV3Ijp7ImVuYWJsZWQiOmZhbHNlLCJpZCI6bnVsbCwibWFya2VyVHlwZSI6InBpbiIsImltYWdlQ29sSWQiOiIifSwiY2FsZW5kYXJWaWV3Ijp7ImVuYWJsZWQiOmZhbHNlLCJzdGFydERhdGVDb2xJZCI6bnVsbCwidGl0bGVDb2xJZCI6Ik5hbWUtIn19"

get_data = requests.get(url)
data = get_data.json()
# print(data)
print("\n")


names = [item["name"] 
         for item in data["table"]["filtersValues"][0]["values"]]

#print(names)
print("\n")
print(len(names))

url2 = "https://spread.name/sheet/Ch-JZHaS1Jr33yDMpDzHjQD1JJAP5FHRF3LI221VGFm-12MzaYevvfCflDPkrrRlLppo?query=eyJnZXRSb3dCeSI6eyJzbHVnIjoiZ2V0c29sdmVkIn19&options=eyJyb3dzTGltaXQiOjUwMDAsImRlYWxUeXBlIjoiYXBwc3VtbyIsImR5bmFtaWNEYXRhIjp7InNoZWV0SGFzaCI6IjE4MDM3NTYzODciLCJTQ1BUYWJsZUxhdGVzdFVwZGF0ZVRpbWVzdGFtcCI6MTc4Nzk5ODI5MDUwOH0sInNlYXJjaCI6eyJlbmFibGVkIjp0cnVlLCJjb2x1bW5zIjpbIk5hbWUtIiwiUHJpY2UtIiwiQ2F0ZWdvcnktIiwiSGFzaHRhZy0iLCJMb25nZGVzY3JpcHRpb24tIl19LCJzb3J0aW5nIjp7ImVuYWJsZWQiOmZhbHNlLCJzaHVmZmxlIjpmYWxzZX0sInBhZ2luYXRpb24iOnsiZW5hYmxlZCI6dHJ1ZSwiaXRlbXNQZXJQYWdlIjoiMTAwIn0sImZpbHRlcnMiOnsiZW5hYmxlZCI6dHJ1ZSwidmFsdWVzIjpbeyJpZCI6Ik5hbWUtIiwidHlwZSI6Im11bHRpcGxlIn0seyJpZCI6IkNhdGVnb3J5LSIsInR5cGUiOiJtdWx0aXBsZSJ9LHsiaWQiOiJQcmljZS0iLCJ0eXBlIjoibXVsdGlwbGUifV19LCJtYXBWaWV3Ijp7ImVuYWJsZWQiOmZhbHNlLCJpZCI6bnVsbCwibWFya2VyVHlwZSI6InBpbiIsImltYWdlQ29sSWQiOiIifSwiY2FsZW5kYXJWaWV3Ijp7ImVuYWJsZWQiOmZhbHNlLCJzdGFydERhdGVDb2xJZCI6bnVsbCwidGl0bGVDb2xJZCI6Ik5hbWUtIn19"

#get_data2 = requests.get(url2)
#data2 = get_data2.json()
#print(data2)



slug = "aiapply"

#slug = "wellows"

query_data = {
    "getRowBy": {
        "slug": slug
    }
}

# dict → JSON string → bytes → Base64 string
query = base64.b64encode(
    json.dumps(query_data, separators=(",", ":")).encode("utf-8")
).decode("utf-8")

print(query)


base_url = "https://spread.name/sheet/Ch-JZHaS1Jr33yDMpDzHjQD1JJAP5FHRF3LI221VGFm-12MzaYevvfCflDPkrrRlLppo"

options = "eyJyb3dzTGltaXQiOjUwMDAsImRlYWxUeXBlIjoiYXBwc3VtbyIsImR5bmFtaWNEYXRhIjp7InNoZWV0SGFzaCI6IjE4MDM3NTYzODciLCJTQ1BUYWJsZUxhdGVzdFVwZGF0ZVRpbWVzdGFtcCI6MTc4Nzk5ODI5MDUwOH0sInNlYXJjaCI6eyJlbmFibGVkIjp0cnVlLCJjb2x1bW5zIjpbIk5hbWUtIiwiUHJpY2UtIiwiQ2F0ZWdvcnktIiwiSGFzaHRhZy0iLCJMb25nZGVzY3JpcHRpb24tIl19LCJzb3J0aW5nIjp7ImVuYWJsZWQiOmZhbHNlLCJzaHVmZmxlIjpmYWxzZX0sInBhZ2luYXRpb24iOnsiZW5hYmxlZCI6dHJ1ZSwiaXRlbXNQZXJQYWdlIjoiMTAwIn0sImZpbHRlcnMiOnsiZW5hYmxlZCI6dHJ1ZSwidmFsdWVzIjpbeyJpZCI6Ik5hbWUtIiwidHlwZSI6Im11bHRpcGxlIn0seyJpZCI6IkNhdGVnb3J5LSIsInR5cGUiOiJtdWx0aXBsZSJ9LHsiaWQiOiJQcmljZS0iLCJ0eXBlIjoibXVsdGlwbGUifV19LCJtYXBWaWV3Ijp7ImVuYWJsZWQiOmZhbHNlLCJpZCI6bnVsbCwibWFya2VyVHlwZSI6InBpbiIsImltYWdlQ29sSWQiOiIifSwiY2FsZW5kYXJWaWV3Ijp7ImVuYWJsZWQiOmZhbHNlLCJzdGFydERhdGVDb2xJZCI6bnVsbCwidGl0bGVDb2xJZCI6Ik5hbWUtIn19"

response = requests.get(
    base_url,
    params={
        "query": query,
        "options": options,   # 先使用你 Network 中原来的 options
    },
    timeout=10
)

response.raise_for_status()
data = response.json()

#print(data)




# 1. 从 API response 取出 URL
url = data["table"]["rows"][0]["cells"]["URL-"]["value"]

# 2. 访问 URL，并自动 follow redirects
r = requests.get(url, allow_redirects=True, timeout=10)
r.raise_for_status()

# 3. 获取最终落地 URL
final_url = r.url

# 4. 去掉 ? 后面的 query parameters
parts = urlsplit(final_url)
official_url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

print(official_url)


# Longdescription-.value 已经包含正文、Applications and Core Features、Bullet Point Features 等内容
description = response["table"]["rows"][0]["cells"]["Longdescription-"]["value"]

print(description)