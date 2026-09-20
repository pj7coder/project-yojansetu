'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { CitizenLanguage, CitizenSchemeDetail } from '@/types/citizen';
import { getCitizenSchemeDetail, ApiError } from '@/lib/api';
import CitizenShell from '@/components/citizen/CitizenShell';
import SchemeDetails from '@/components/citizen/SchemeDetails';

export default function SchemeDetailPage() {
  const params = useParams();
  const schemeId = params?.schemeId as string;

  const [language, setLanguage] = useState<CitizenLanguage>('hi');
  const [scheme, setScheme] = useState<CitizenSchemeDetail | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isInactive, setIsInactive] = useState<boolean>(false);

  const isHi = language === 'hi';

  useEffect(() => {
    if (!schemeId) return;

    const fetchDetail = async () => {
      setIsLoading(true);
      setErrorMessage(null);
      setIsInactive(false);

      try {
        const data = await getCitizenSchemeDetail(schemeId);
        setScheme(data);
      } catch (err: any) {
        if (err instanceof ApiError && err.statusCode === 404) {
          setIsInactive(true);
          setErrorMessage(
            isHi
              ? 'यह योजना या इसका संस्करण वर्तमान में सक्रिय नहीं है।'
              : 'This scheme or version is not currently active.'
          );
        } else {
          setErrorMessage(
            isHi
              ? 'योजना की जानकारी लोड करने में त्रुटि हुई।'
              : 'Failed to load scheme details.'
          );
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchDetail();
  }, [schemeId, isHi]);

  return (
    <CitizenShell
      language={language}
      onLanguageChange={setLanguage}
      showStartOver={false}
    >
      <div className="w-full max-w-3xl mx-auto space-y-6">
        {/* Navigation link */}
        <div>
          <Link
            href="/citizen"
            className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-700 hover:text-emerald-800 transition py-1"
          >
            ← {isHi ? 'योजना खोज पर वापस जाएँ' : 'Back to Scheme Discovery'}
          </Link>
        </div>

        {isLoading && (
          <div className="bg-white rounded-3xl p-12 border border-slate-200 text-center space-y-4">
            <div className="w-10 h-10 border-3 border-emerald-600 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-sm font-medium text-slate-600">
              {isHi
                ? 'योजना की सत्यापित जानकारी लोड हो रही है…'
                : 'Loading verified scheme details…'}
            </p>
          </div>
        )}

        {isInactive && (
          <div className="bg-white rounded-3xl p-8 border border-amber-200 text-center max-w-lg mx-auto space-y-4 shadow-sm">
            <div className="w-14 h-14 bg-amber-50 text-amber-600 rounded-full flex items-center justify-center mx-auto">
              <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h3 className="text-xl font-bold text-slate-900">
              {isHi ? 'योजना सक्रिय नहीं है' : 'Scheme Not Active'}
            </h3>
            <p className="text-slate-600 text-sm leading-relaxed">
              {errorMessage ||
                (isHi
                  ? 'यह योजना या संस्करण वर्तमान में सक्रिय नहीं है।'
                  : 'This scheme/version is not currently active.')}
            </p>
            <div className="pt-2">
              <Link
                href="/citizen"
                className="px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-xl inline-block shadow-sm transition"
              >
                {isHi ? 'सक्रिय योजनाएँ खोजें' : 'Discover Active Schemes'}
              </Link>
            </div>
          </div>
        )}

        {errorMessage && !isInactive && (
          <div className="bg-white rounded-3xl p-8 border border-rose-200 text-center max-w-lg mx-auto space-y-4 shadow-sm">
            <div className="w-14 h-14 bg-rose-50 text-rose-600 rounded-full flex items-center justify-center mx-auto">
              <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h3 className="text-xl font-bold text-slate-900">
              {isHi ? 'त्रुटि' : 'Error'}
            </h3>
            <p className="text-slate-600 text-sm leading-relaxed">{errorMessage}</p>
            <div className="pt-2">
              <Link
                href="/citizen"
                className="px-6 py-3 bg-slate-800 hover:bg-slate-900 text-white font-semibold rounded-xl inline-block shadow-sm transition"
              >
                {isHi ? 'पुनः प्रयास करें' : 'Try Again'}
              </Link>
            </div>
          </div>
        )}

        {scheme && !isLoading && (
          <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-sm">
            <SchemeDetails scheme={scheme} language={language} />
          </div>
        )}
      </div>
    </CitizenShell>
  );
}
