#!/bin/bash
URL="http://127.0.0.1:5000/shop"
WYNIKI="wyniki_pelne_$(date +%Y%m%d_%H%M).csv"
echo "uzytkownicy,trans_sek,sr_czas_s,najdluzszy_s,dostepnosc_pct" > $WYNIKI

for USERS in 50 100 150 200 250 300 350 400 450 500 650 800 950 1100 1250 1400 1550 1700 1850 2000; do
    echo ">>> Test: $USERS uzytkownikow..."

    psql -h localhost -U postgres -d system_biletowy -c \
        "SELECT pg_stat_statements_reset();" > /dev/null

    RAW=$(siege -c $USERS -t 15S --no-parser -q "$URL" 2>&1)

    TRANS_SEK=$(echo "$RAW" | grep "transaction_rate"    | awk -F: '{print $2}' | tr -d ' ,')
    SR_CZAS=$(echo "$RAW"   | grep "response_time"       | awk -F: '{print $2}' | tr -d ' ,')
    NAJDL=$(echo "$RAW"     | grep "longest_transaction" | awk -F: '{print $2}' | tr -d ' ,')
    DOSTEP=$(echo "$RAW"    | grep "availability"        | awk -F: '{print $2}' | tr -d ' ,')

    echo "$USERS,$TRANS_SEK,$SR_CZAS,$NAJDL,$DOSTEP" >> $WYNIKI
    echo "    trans/s: $TRANS_SEK | avg: ${SR_CZAS}s | max: ${NAJDL}s | dostepnosc: $DOSTEP%"

    sleep 10
done

echo ""
echo "=== GOTOWE ==="
cat $WYNIKI
