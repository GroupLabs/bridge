import { NextResponse } from "next/server";

export async function GET() {
  // const jsonBody = [
  //   {
  //     url: "https://br.linkedin.com/in/aldo-soares-7b886482/en",
  //     title: "Jean Silva - Brasília, Federal District, Brazil",
  //     description:
  //       "Senior Java Software Engineer. Montreal TI. MDS - Ministério do Desenvolvimento Social e Combate à Fome. Dec 2016 - Apr 2017 5 months. Brasília, Brazil.",
  //   },
  //   {
  //     url: "https://br.linkedin.com/in/fbcouto/pt",
  //     title: "FERNANDO BELMIRO COUTO - Senior Software Engineer",
  //     description:
  //       "Experiência · Senior Software Engineer · Full-stack Developer · analista de sistemas senior · Analista de Sistemas Pleno · Gerente de Expediente · Gerente de ...",
  //   },
  //   {
  //     url: "https://br.linkedin.com/in/guilherme-cafure",
  //     title: "Guilherme Nascimento Cafure - Software Engineer",
  //     description:
  //       "Providing Services for BDMG: (Banco de Desenvolvimento de Minas Gerais). - Development of full applications using Java/Spring framework;",
  //   },
  //   {
  //     url: "https://br.linkedin.com/in/luiz-shonen/en",
  //     title: "Luiz Rodrigues - Mid-level Software Engineer",
  //     description:
  //       "I'm Luiz Rodrigues, I'm a Software Engineer at Montral Informática, currently working for BDMG (Development Bank of the state of Minas Gerais), ...",
  //   },
  //   {
  //     url: "https://www.linkedin.com/in/ilias-ermides-94a917107",
  //     title: "Ilias Ermides - Software Engineer - Montreal Oficial",
  //     description:
  //       "View Ilias Ermides' profile on LinkedIn, the world's largest professional community. Ilias has 2 jobs listed on their profile. See the complete profile on ...",
  //   },
  //   {
  //     url: "https://in.linkedin.com/in/patrick-fincham-5bb452154",
  //     title: "Patrick Fincham - Software Engineer - Montreal Graphic ...",
  //     description:
  //       "Patrick Fincham. Software Engineer at Montreal Graphic Design. Montreal Graphic Design. West Delhi, Delhi, India. 1 follower. See your mutual connections ...",
  //   },
  // ];

  const transformedJsonBody = [
    {
      name: "Jean Silva",
      title: "Senior Java Software Engineer",
      description:
        "Senior Java Software Engineer. Montreal TI. MDS - Ministério do Desenvolvimento Social e Combate à Fome. Dec 2016 - Apr 2017 5 months. Brasília, Brazil.",
      monthsAgo: 1,
      country: "Brazil",
      region: "Distrito Federal",
      url: "https://br.linkedin.com/in/aldo-soares-7b886482/en",
    },
    {
      name: "FERNANDO BELMIRO COUTO",
      title: "Senior Software Engineer",
      description:
        "Experiência · Senior Software Engineer · Full-stack Developer · analista de sistemas senior · Analista de Sistemas Pleno · Gerente de Expediente · Gerente de ...",
      monthsAgo: 3,
      country: "Brazil",
      region: "",
      url: "https://br.linkedin.com/in/fbcouto/pt",
    },
    {
      name: "Guilherme Nascimento Cafure",
      title: "Software Engineer",
      description:
        "Providing Services for BDMG: (Banco de Desenvolvimento de Minas Gerais). - Development of full applications using Java/Spring framework;",
      monthsAgo: 3,
      country: "Brazil",
      region: "Minas Gerais",
      url: "https://br.linkedin.com/in/guilherme-cafure",
    },
    {
      name: "Luiz Rodrigues",
      title: "Mid-level Software Engineer",
      description:
        "I'm Luiz Rodrigues, I'm a Software Engineer at Montral Informática, currently working for BDMG (Development Bank of the state of Minas Gerais), ...",
      monthsAgo: 1,
      country: "Brazil",
      region: "Minas Gerais",
      url: "https://br.linkedin.com/in/luiz-shonen/en",
    },
    {
      name: "Ilias Ermides",
      title: "Software Engineer",
      description:
        "View Ilias Ermides' profile on LinkedIn, the world's largest professional community. Ilias has 2 jobs listed on their profile. See the complete profile on ...",
      monthsAgo: 6,
      country: "",
      region: "",
      url: "https://www.linkedin.com/in/ilias-ermides-94a917107",
    },
    {
      name: "Patrick Fincham",
      title: "Software Engineer",
      description:
        "Patrick Fincham. Software Engineer at Montreal Graphic Design. Montreal Graphic Design. West Delhi, Delhi, India. 1 follower. See your mutual connections ...",
      monthsAgo: 12,
      country: "India",
      region: "Delhi",
      url: "https://in.linkedin.com/in/patrick-fincham-5bb452154",
    },
  ];

  return new NextResponse(JSON.stringify(transformedJsonBody), {
    headers: { "Content-Type": "application/json" },
  });
}
