@echo off
rem v1.0.0
rem ���۴��������д˽ű������Ƚ���ǰĿ¼�л����ű����ڵ�Ŀ¼��
cd /d %~dp0

chcp 936 > nul
setlocal

echo =======================================================
echo           �Զ������Կ�ܻ���һ����װ�ű�
echo =======================================================
echo.

rem ���徵��Դ��ַ
set PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

rem ��� Python ����
echo ���ڼ�� Python ����...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [����] δ�ڱ����ҵ� Python����ӹ��� python.org ���ز���װ Python 3.8+��
    pause
    exit /b
)
echo Python �Ѱ�װ��

rem �������⻷��
echo.
echo ���ڴ��� Python ���⻷�� (.venv)...
if not exist .venv (
    python -m venv .venv
)
echo ���⻷���Ѵ�����

rem ���������¹��ܣ�����pip��������
echo.
echo ����ʹ���廪����Դ���� pip ����...
call .\.venv\Scripts\activate.bat && python -m pip install --upgrade pip -i %PIP_INDEX_URL%
if %errorlevel% neq 0 (
    echo [����] pip ����ʧ�ܣ�������ʹ�õ�ǰ�汾��
) else (
    echo pip �ѳɹ����������°汾��
)

rem �������⻷����ʹ�þ���Դ��װ����
echo.
echo ����ʹ���廪����Դ��װ������Ŀ������ (������Ҫ������)...
call .\.venv\Scripts\activate.bat && pip install -r requirements.txt -i %PIP_INDEX_URL%
if %errorlevel% neq 0 (
    echo [����] ������װʧ�ܡ������������ϵ��ܹ���Ա��
    pause
    exit /b
)
echo �����������Ѱ�װ�ɹ���

rem ��װ Playwright ���������
echo.
echo �������� Playwright ��������� (�������Ҫ�ϳ�ʱ�䣬�����ĵȴ�)...
call .\.venv\Scripts\activate.bat && playwright install
if %errorlevel% neq 0 (
    echo [����] �������������ʧ�ܡ������������ϵ��ܹ���Ա��
    pause
    exit /b
)
echo ����������ѳɹ���װ��

echo.
echo =======================================================
echo           ������׼������! ���������в�����!
echo =======================================================
echo.
pause
endlocal
