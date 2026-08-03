-- Corrige registros gravados com o bug BrandId 171 → "ticket" (oficial = Elo).
-- Rodar no Postgres staging após atualizar o código do consumer.
-- Depois: reprocessar DLQ no portal (Mapeamentos Elo Crédito = Tasy 10).

UPDATE registro_maquininha
SET
    cd_bandeira = 'elo',
    ds_obs_processo = CASE
        WHEN cd_status IN (6, 7)
             AND ds_obs_processo ILIKE '%credit_card/ticket%'
        THEN 'Corrigido bandeira ticket→elo (BrandId 171). Reprocesse.'
        ELSE ds_obs_processo
    END,
    dt_atualizacao = NOW()
WHERE LOWER(COALESCE(cd_bandeira, '')) = 'ticket';
