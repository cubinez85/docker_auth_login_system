#!/bin/bash
# full_auth_test.sh

BASE_URL="http://127.0.0.1:8000"
EMAIL="test6@cubinez.ru"
PASS="TestPass123"

echo "=== 1. Login ==="
LOGIN_RESP=$(curl -s -X POST "$BASE_URL/api/auth/login/" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}")
echo "$LOGIN_RESP" | python3 -m json.tool

ACCESS_TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")
REFRESH_TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('refresh_token',''))")

if [ -z "$ACCESS_TOKEN" ]; then
    echo "❌ Failed to get access token"
    exit 1
fi

echo -e "\n=== 2. Update profile (PUT) ==="
curl -s -X PUT "$BASE_URL/api/auth/profile/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{"last_name":"Updated","first_name":"Tester","middle_name":"Middle"}' | python3 -m json.tool

echo -e "\n=== 3. Refresh token ==="
curl -s -X POST "$BASE_URL/api/auth/refresh/" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}" | python3 -m json.tool

echo -e "\n=== 4. Logout ==="
curl -s -X POST "$BASE_URL/api/auth/logout/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool

echo -e "\n=== 5. Try access with blacklisted token (should be 401) ==="
curl -s -w "\nHTTP Status: %{http_code}\n" -X PUT "$BASE_URL/api/auth/profile/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{}' | head -5

echo -e "\n=== 6. Login again for delete test ==="
LOGIN_RESP2=$(curl -s -X POST "$BASE_URL/api/auth/login/" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}")
NEW_TOKEN=$(echo "$LOGIN_RESP2" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

echo -e "\n=== 7. Delete profile (soft delete) ==="
curl -s -X DELETE "$BASE_URL/api/auth/profile/" \
  -H "Authorization: Bearer $NEW_TOKEN" | python3 -m json.tool

echo -e "\n=== 8. Try login with deleted account (should fail) ==="
curl -s -X POST "$BASE_URL/api/auth/login/" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" | python3 -m json.tool

echo -e "\n✅ All tests completed!"
